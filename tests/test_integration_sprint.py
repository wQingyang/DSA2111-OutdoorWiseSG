"""Integration boundaries use temporary data and mocked external providers."""
import json
import shutil
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.environment import IngestionRun, utc_now
from outdoorwise.llm.models import ParsedRouteRequest
from outdoorwise.llm.parser import parse_route_request
from outdoorwise.services.live_prediction import LivePredictionService


@pytest.fixture
def live(tmp_path):
    shutil.copytree(ROOT / 'data/catalog', tmp_path / 'catalog')
    pipeline = build_pipeline(Settings(data_root=tmp_path, data_mode='demo'))
    now = utc_now().replace(microsecond=0)
    for collector in pipeline.collectors:
        batch, _ = collector.collect()
        batch = batch.model_copy(update={'fetched_at': now, 'locations': [
            loc.model_copy(update={'source_kind': 'live'}) for loc in batch.locations],
            'observations': [obs.model_copy(update={'source_kind': 'live', 'observed_at': now,
                'fetched_at': now, 'first_fetched_at': now, 'source_updated_at': now}) for obs in batch.observations]})
        pipeline.repository.ingest(batch, IngestionRun(run_id=collector.source, source=collector.source,
            source_kind='live', started_at=now, finished_at=now, status='success'))
    return pipeline, now


def service(pipeline, mode='live'):
    return LivePredictionService(pipeline.repository, pipeline.config, mode)


def test_live_prediction_coverage_provenance_and_no_retraining(live):
    pipeline, now = live
    result = service(pipeline).predict('marina_bay', 0, 30, now)
    assert result['mode'] == 'live_supplementary_forecast'
    metrics = {item.metric: item for item in result['metrics']}
    assert metrics['pm25'].covers_entire_run
    assert not metrics['rainfall'].covers_entire_run
    assert metrics['rainfall'].covered_minutes == 5
    assert metrics['wbgt'].covered_minutes == 15
    for item in metrics.values():
        assert item.method == 'persistence' and not item.validated
        assert item.first_fetched_at <= now
        assert item.input_observation_timestamps == [now]
        assert item.source_location_id and item.revision == 1
        assert item.model_version == 'persistence-v1'
    later = service(pipeline).predict('marina_bay', 120, 30, now)
    assert all(not item.covers_entire_run and item.covered_minutes == 0 for item in later['metrics'])


def test_live_prediction_stale_missing_and_demo_are_unavailable(live):
    pipeline, now = live
    stale = service(pipeline).predict('marina_bay', 0, 30, now + timedelta(days=1))
    future = service(pipeline).predict('marina_bay', 0, 30, now - timedelta(seconds=1))
    demo = service(pipeline, 'demo').predict('marina_bay', 0, 30, now)
    for result in [stale, future, demo]:
        assert all(item.method == 'unavailable' and item.value is None and item.missing_reasons
                   and not item.covers_entire_run for item in result['metrics'])


def test_live_prediction_revision_asof(live):
    pipeline, now = live
    from outdoorwise.contracts.environment import CollectionBatch
    locations, observations, _ = pipeline.repository.environment_snapshot('live', now)
    source = 'nea_pm25'
    revised = now + timedelta(minutes=1)
    batch = CollectionBatch(source=source, fetched_at=revised,
        locations=[loc for loc in locations if loc.source == source],
        observations=[obs.model_copy(update={'fetched_at': revised, 'value': 999})
                      for obs in observations if obs.source == source])
    pipeline.repository.ingest(batch, IngestionRun(run_id='revision', source=source, source_kind='live',
        started_at=revised, finished_at=revised, status='success'))
    before = next(item for item in service(pipeline).predict('marina_bay', 0, 30, now)['metrics'] if item.metric == 'pm25')
    after = next(item for item in service(pipeline).predict('marina_bay', 0, 30, revised)['metrics'] if item.metric == 'pm25')
    assert before.value != 999 and before.revision == 1
    assert after.value == 999 and after.revision == 2 and after.first_fetched_at == revised


def test_live_and_historical_endpoints_are_separate(live, monkeypatch):
    pipeline, _ = live
    app = create_app(Settings(data_root=pipeline.repository.root, data_mode='live'))
    monkeypatch.setattr('outdoorwise.api.time_selection.historical_forecast', lambda *args: {'mode': 'historical_snapshot_replay', 'as_of': '2026-10-15T19:15:00+08:00'})
    with TestClient(app) as client:
        payload = {'route_id': 'marina_bay'}
        assert client.post('/api/time-selection/forecast', json=payload).json()['mode'] == 'historical_snapshot_replay'
        response = client.post('/api/time-selection/live-forecast', json=payload)
        assert response.json()['mode'] == 'live_supplementary_forecast'
        assert response.headers['cache-control'] == 'no-store'
        assert client.post('/api/time-selection/live-forecast', json={'route_id': 'unknown'}).status_code == 404
        assert client.post('/api/time-selection/live-forecast', json={**payload, 'duration_min': 61, 'start_delay_min': 120}).status_code == 422
        assert client.get('/api/health').json()['data_mode'] == 'live'
        assert client.get('/api/ready').status_code == 200
        assert 'agent_mode' not in client.get('/api/health').json()
        assert '/api/chat' not in client.get('/openapi.json').json()['paths']


@pytest.mark.parametrize('content', ['', 'not JSON', '{"target_distance_km": 500}', '{"preferences": {"prefer_green": "yes"}}', '{"coordinates": [1, 2]}'])
def test_parser_rejects_invalid_provider_outputs(monkeypatch, content):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    stub = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs:
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))]))))
    monkeypatch.setattr('outdoorwise.llm.parser.OpenAI', lambda **kwargs: stub)
    with pytest.raises(ValueError): parse_route_request('run near NUS')


def test_parser_success_and_api_failures(live, monkeypatch):
    pipeline, _ = live
    app = create_app(Settings(data_root=pipeline.repository.root, data_mode='live'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    with TestClient(app) as client:
        assert client.post('/api/llm/parse', json={'text': 'NUS run'}).status_code == 503
        monkeypatch.setenv('OPENROUTER_API_KEY', 'server-secret')
        monkeypatch.setattr('outdoorwise.llm.router.parse_route_request', lambda text: ParsedRouteRequest(location='NUS'))
        result = client.post('/api/llm/parse', json={'text': 'NUS run'})
        assert result.status_code == 200 and result.json()['location'] == 'NUS'
        assert 'server-secret' not in result.text
        assert client.post('/api/llm/parse', json={'text': '   '}).status_code == 422
        def failing(text): raise TimeoutError('private provider details server-secret')
        monkeypatch.setattr('outdoorwise.llm.router.parse_route_request', failing)
        failed = client.post('/api/llm/parse', json={'text': 'NUS run'})
        assert failed.status_code == 502 and 'server-secret' not in failed.text


def test_historical_rainfall_does_not_fit_models():
    import sys
    sys.path.insert(0, str(ROOT / 'prediction'))
    from predict_route_environment import rain_forecasts
    rows = rain_forecasts({}, None, utc_now())
    assert all(row['value'] is None for row in rows)
    assert all(row['method'] == 'missing_rainfall_input' for row in rows[:2])
    assert all(row['method'] == 'unsupported_rainfall_horizon' for row in rows[2:])


def test_pm25_artifact_inventory():
    rows = json.loads((ROOT / 'prediction/results/pm25_multihorizon/backtest_models.json').read_text())
    assert len(rows) == 15
    assert {row['horizon_min'] for row in rows} == {60, 120, 180}
    assert {row['training_cutoff'] for row in rows} == {'2026-10-14T00:00:00+08:00'}
    assert all(len(row['linear_intercept_and_coefficients']) == 4 for row in rows)


def test_collector_heartbeat(tmp_path):
    from outdoorwise.pipeline.collector_health import healthy
    now = utc_now()
    assert not healthy(tmp_path, now)
    (tmp_path / 'runtime').mkdir()
    path = tmp_path / 'runtime/collection_worker.json'
    path.write_text(json.dumps({'state': 'running', 'updated_at': now.isoformat()}))
    assert healthy(tmp_path, now)
    assert not healthy(tmp_path, now + timedelta(hours=1))
    path.write_text('broken')
    assert not healthy(tmp_path, now)


def test_real_parser_accepts_validated_json_only(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    payload = {'location': 'NUS', 'target_distance_km': 5.5, 'target_difficulty': 2,
               'preferences': {'prefer_green': True, 'prefer_quiet': False, 'avoid_steps': True}}
    def factory(**settings):
        assert settings['base_url'] == 'https://openrouter.ai/api/v1'
        assert settings['timeout'] == 30 and settings['max_retries'] == 1
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs:
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='```json\n' + json.dumps(payload) + '\n```'))]))))
    monkeypatch.setattr('outdoorwise.llm.parser.OpenAI', factory)
    assert parse_route_request('NUS 5.5 km').model_dump() == payload


def test_synthetic_fixture_copy_refuses_existing_data(tmp_path):
    from scripts.copy_synthetic_fixture import copy_fixture
    target = tmp_path / 'demo'
    copy_fixture(target)
    assert (target / 'catalog/routes.csv').is_file()
    import sqlite3
    with sqlite3.connect(target / 'runtime/accounts.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 2
    with pytest.raises(ValueError, match='must not exist'): copy_fixture(target)
