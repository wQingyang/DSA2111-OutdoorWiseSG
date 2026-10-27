"""Unified dispatcher integration against temporary storage and frozen replay."""
import hashlib
import shutil
from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.api.time_selection import REPLAY_TIME
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.environment import timestamp


@pytest.fixture
def settings(tmp_path):
    shutil.copytree(ROOT / 'data/catalog', tmp_path / 'catalog')
    return Settings(data_root=tmp_path, data_mode='live')


def hashes(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def test_app_mode_environment(monkeypatch):
    monkeypatch.delenv('OUTDOORWISE_APP_MODE', raising=False)
    assert Settings.from_env().app_mode == 'live'
    for mode in ('live', 'historical'):
        monkeypatch.setenv('OUTDOORWISE_APP_MODE', mode)
        assert Settings.from_env().app_mode == mode
    monkeypatch.setenv('OUTDOORWISE_APP_MODE', 'forecast')
    with pytest.raises(ValueError, match='OUTDOORWISE_APP_MODE must be live or historical'):
        Settings.from_env()
    with pytest.raises(ValueError, match='OUTDOORWISE_APP_MODE'):
        Settings(app_mode='bad')


@pytest.mark.parametrize('mode', ['live', 'historical'])
def test_health_frontend_and_validation(settings, mode):
    with TestClient(create_app(replace(settings, app_mode=mode))) as client:
        assert client.get('/api/health').json()['app_mode'] == mode
        assert client.get('/api/health').json()['data_mode'] == 'live'
        page = client.get('/').text
        assert 'Find Recommended Routes' in page
        assert 'forecast-launcher' not in page
        assert 'live-forecast.js' not in page
        assert 'value="120"' not in page
        assert client.post('/api/route-recommendations', json={'start_delay_min': 120}).status_code == 422
        if mode == 'live':
            for delay in (30, 60):
                response = client.post('/api/route-recommendations', json={'start_delay_min': delay})
                assert response.status_code == 422
                assert 'Now' in response.json()['detail']


def test_live_uses_current_pipeline_and_no_historical_inference(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Live requests must not invoke replay or supplementary prediction')
    monkeypatch.setattr('outdoorwise.api.recommendation_workflow.rank_historical', forbidden)
    monkeypatch.setattr('outdoorwise.services.live_prediction.LivePredictionService.predict', forbidden)
    with TestClient(create_app(settings)) as client:
        result = client.post('/api/route-recommendations', json={})
        assert result.status_code == 200
        data = result.json()
        assert data['assessment_type'] == 'observed'
        assert data['environmental_source'] == 'live_repository'
        assert data['requested_departure_offset_min'] == 0
        assert data['recommendations']
        assert all(row['risk_score'] is None for row in data['recommendations'])
        assert all(row['eligibility'] == 'unknown' for row in data['recommendations'])
        assert all(metric['value'] is None for env in data['environment'] for metric in env['metrics'])
        assert not data.get('prediction_details')


@pytest.mark.parametrize('delay', [0, 30, 60])
def test_historical_origin_window_isolation_and_coverage(settings, monkeypatch, delay):
    app = create_app(replace(settings, app_mode='historical'))
    def forbidden(*args, **kwargs):
        raise AssertionError('Historical recommendations cannot run or refresh the operational pipeline')
    monkeypatch.setattr(app.state.pipeline, 'run', forbidden)
    monkeypatch.setattr(app.state.pipeline, 'refresh', forbidden)
    monkeypatch.setattr(app.state.pipeline.repository, 'environment_snapshot', forbidden)
    with TestClient(app) as client:
        before = hashes(settings.data_root)
        response = client.post('/api/route-recommendations', json={'start_delay_min': delay, 'duration_min': 30})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['app_mode'] == 'historical'
        assert data['assessment_type'] == ('historical_observation' if delay == 0 else 'forecast_based')
        assert timestamp(data['assessment_reference_time']) == timestamp(REPLAY_TIME)
        assert timestamp(data['run_start']) == timestamp(REPLAY_TIME) + timedelta(minutes=delay)
        assert timestamp(data['run_end']) == timestamp(REPLAY_TIME) + timedelta(minutes=delay+30)
        assert len(data['routes']) == 12
        assert data['recommendations']
        assert all((row['risk_score'] is not None and row['recommendation_score'] is not None) if delay == 0 else (row['risk_score'] is None and row['recommendation_score'] is None) for row in data['recommendations'])
        assert all(row['full_run_assessment']['risk_score'] is None for row in data['recommendations'])
        for forecast in data['prediction_details'].values():
            for metric in forecast['metrics'].values():
                assert not metric['covers_entire_run']
                for block in metric['blocks']:
                    for source in block.get('input_provenance', []):
                        assert timestamp(source['observed_at']) <= timestamp(REPLAY_TIME)
                        assert timestamp(source['available_at']) <= timestamp(REPLAY_TIME)
                    if block['ground_truth']:
                        assert block['ground_truth']['usage'] == 'evaluation_only'
                        assert timestamp(block['ground_truth']['observed_at']) > timestamp(REPLAY_TIME)
                    else:
                        assert block['forecast_error'] is None
            assert all(row['value'] is None for row in forecast['metrics']['rain_probability']['blocks'])
        assert hashes(settings.data_root) == before


@pytest.mark.parametrize('mode', ['live', 'historical'])
def test_unified_session_isolation_and_generic_fallback(settings, mode):
    with TestClient(create_app(replace(settings, app_mode=mode))) as client:
        generic = client.post('/api/route-recommendations', json={}).json()
        assert not generic['personalized']
        client.cookies.set('outdoorwise_session', 'invalid')
        assert client.post('/api/route-recommendations', json={}).status_code == 401
        client.cookies.clear()
        user_results = []
        for name in ('runner_one', 'runner_two'):
            account = client.post('/api/auth/register', json={'username': name, 'password': 'password123'})
            assert account.status_code == 201
            response = client.post('/api/route-recommendations', json={})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data['personalized']
            user_results.append(data)
            # Recommendation itself never creates completed runs or feedback.
            user = account.json()['user_id']
            assert client.get(f'/api/users/{user}/runs').json() == []
            assert client.get(f'/api/users/{user}/feedback').json() == []
            assert {row['route_id'] for row in data['recommendations']} == {row['route_id'] for row in generic['recommendations']}
            client.post('/api/auth/logout')
        assert [r['route_id'] for r in user_results[0]['recommendations']] == [r['route_id'] for r in user_results[1]['recommendations']]


def test_historical_missing_pm25_artifact_uses_explicit_baseline(settings, monkeypatch):
    from outdoorwise.api.time_selection import historical_forecast
    # Load research modules through their existing compatibility import boundary.
    historical_forecast('marina_bay', 0, 30)
    import predict_route_environment as environment
    original = type(ROOT).exists
    monkeypatch.setattr(type(ROOT), 'exists', lambda path: False if path.name == 'backtest_models.json' else original(path))
    data = environment.predict('marina_bay', timestamp(REPLAY_TIME), 0, 30)
    assert all(block['method'] in {'persistence_fallback', 'missing_input_or_model'} for block in data['metrics']['pm25']['blocks'])
    assert all(block['model_version'] == 'unavailable' for block in data['metrics']['pm25']['blocks'])


def test_exact_target_evaluation_never_changes_inference(monkeypatch):
    from outdoorwise.api.historical_evidence import describe_forecast
    target = timestamp(REPLAY_TIME) + timedelta(minutes=15)
    raw = {'as_of': REPLAY_TIME, 'run_start': REPLAY_TIME, 'run_end': target.isoformat(),
           'sources': {'wbgt': {'station_id': 'S124'}},
           'metrics': {'wbgt': {'unit': 'degC', 'model_origin': REPLAY_TIME,
                'blocks': [{'valid_from': REPLAY_TIME, 'valid_to': target.isoformat(), 'value': 29, 'method': 'persistence'}]}},
           'forecast_risk': {'risk_score': 10, 'components': {'heat': {'score': 10}}}}
    truth = dict(value='30', observed_at=target.isoformat(), fetched_at=target.isoformat(),
                 source_updated_at=target.isoformat(), source='nea_wbgt', unit='degC', aggregation_window='PT15M')
    monkeypatch.setattr('outdoorwise.api.historical_evidence.evaluation_records', lambda: {('wbgt', 'S124', target): truth})
    result = describe_forecast(raw)
    block = result['metrics']['wbgt']['blocks'][0]
    assert block['forecast_error'] == -1
    assert block['ground_truth']['usage'] == 'evaluation_only'
    assert block['value'] == 29
    assert result['forecast_risk']['risk_score'] is None
    assert raw['forecast_risk']['risk_score'] == 10  # cached research payload is never mutated
    truth['value'] = '99'
    changed = describe_forecast(raw)
    assert changed['metrics']['wbgt']['blocks'][0]['value'] == 29
    assert changed['forecast_risk'] == result['forecast_risk']


def test_unified_live_matches_existing_current_observation_ranking(settings):
    from outdoorwise.contracts.environment import IngestionRun, utc_now
    from outdoorwise.bootstrap import build_pipeline
    demo = build_pipeline(replace(settings, data_mode='demo'))
    now = utc_now().replace(microsecond=0)
    for collector in demo.collectors:
        batch, _ = collector.collect()
        batch = batch.model_copy(update={'fetched_at': now, 'locations': [
            loc.model_copy(update={'source_kind': 'live'}) for loc in batch.locations],
            'observations': [obs.model_copy(update={'source_kind': 'live', 'observed_at': now,
                'fetched_at': now, 'first_fetched_at': now, 'source_updated_at': now}) for obs in batch.observations]})
        demo.repository.ingest(batch, IngestionRun(run_id=collector.source, source=collector.source,
            source_kind='live', started_at=now, finished_at=now, status='success'))
    with TestClient(create_app(settings)) as client:
        current = client.post('/api/recommendations', json={}).json()
        unified = client.post('/api/route-recommendations', json={}).json()
        fields = ('route_id', 'risk_score', 'recommendation_score', 'final_rank', 'eligibility')
        assert [{key: row[key] for key in fields} for row in unified['recommendations']] == [
            {key: row[key] for key in fields} for row in current['recommendations']]
        assert any(row['risk_score'] is not None for row in unified['recommendations'])
        for env in unified['environment']:
            for metric in env['metrics']:
                if metric['value'] is not None:
                    assert timestamp(metric['observed_at']) == now


def test_replay_filters_future_runs_feedback_and_other_users(settings):
    from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback
    app = create_app(replace(settings, app_mode='historical'))
    origin = timestamp(REPLAY_TIME)
    with TestClient(app) as client:
        account = client.post('/api/auth/register', json={'username': 'replay_runner', 'password': 'password123'}).json()
        user_id = account['user_id']
        empty = client.post('/api/route-recommendations', json={}).json()
        repository = app.state.personalization_service.repository
        for owner, completed, feedback_at, run_id in [
            (user_id, origin + timedelta(minutes=1), origin - timedelta(minutes=1), 'future-run'),
            (user_id, origin - timedelta(days=1), origin + timedelta(minutes=1), 'future-feedback'),
            ('another-user', origin - timedelta(days=1), origin - timedelta(minutes=1), 'other-user'),
        ]:
            repository.save_completed_run(CompletedRun(user_id=owner, completed_run_id=run_id,
                route_id='marina_bay', completed_at=completed, actual_distance_km=4, actual_duration_min=30, predicted_difficulty=1))
            repository.save_feedback(DifficultyFeedback(user_id=owner, feedback_id=run_id,
                route_id='marina_bay', completed_run_id=run_id, created_at=feedback_at, difficulty=5))
        seen = []
        adjust = app.state.personalization_service.adjust_difficulty
        def inspect(user, route, generic, runs, feedback, profile):
            seen.append(([run.completed_run_id for run in runs], [item.feedback_id for item in feedback]))
            return adjust(user, route, generic, runs, feedback, profile)
        app.state.personalization_service.adjust_difficulty = inspect
        before = hashes(settings.data_root)
        result = client.post('/api/route-recommendations', json={})
        assert result.status_code == 200, result.text
        assert seen and all(runs == ['future-feedback'] and not feedback for runs, feedback in seen)
        assert hashes(settings.data_root) == before
        assert {row['route_id'] for row in result.json()['recommendations']} == {row['route_id'] for row in empty['recommendations']}


@pytest.mark.parametrize('mode', ['live', 'historical'])
def test_tab2_always_uses_current_environment(settings, mode, monkeypatch):
    from test_dynamic_routing import StubRoutingClient, generation_request
    from outdoorwise.routing.service import DynamicRouteService
    app = create_app(replace(settings, app_mode=mode))
    app.state.dynamic_routes = DynamicRouteService(StubRoutingClient(), app.state.generated_route_repository)
    def forbidden(*args, **kwargs):
        raise AssertionError('Tab 2 must never invoke historical forecasts')
    monkeypatch.setattr('outdoorwise.api.recommendation_workflow.rank_historical', forbidden)
    monkeypatch.setattr('outdoorwise.api.time_selection.historical_forecast', forbidden)
    with TestClient(app) as client:
        response = client.post('/api/generated-routes', json=generation_request().model_dump(mode='json'))
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data['candidates']) == 2
        assert all(timestamp(row['environmental_risk']['assessed_at']) > timestamp(REPLAY_TIME) for row in data['assessments'])
        assert all(row['environmental_risk']['risk_score'] is None for row in data['assessments'])
        route_id = data['candidates'][0]['route_id']
        assert client.get(f'/api/generated-routes/{route_id}/export.gpx').status_code == 200
