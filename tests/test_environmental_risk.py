"""Synthetic conditions only; never reads or changes local observation history."""
from datetime import datetime, timedelta, timezone
import shutil

import pytest
from pydantic import ValidationError

from outdoorwise.config import ROOT, Settings, load_environment_config
from outdoorwise.contracts.environment import METRIC_SPECS, RouteEnvironment, RouteMetric
from outdoorwise.contracts.models import Conditions, LineString, Prediction, Preferences, Route
from outdoorwise.contracts.risk import BlockingRule, Curve, RankingConfig, RiskConfig
from outdoorwise.modules.recommender import BaselineRecommender
from outdoorwise.modules.risk import EnvironmentalRiskAssessor, normalize
from outdoorwise.modules.risk_ranking import RiskAwareRanking

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return load_environment_config(ROOT / 'config/environment.toml')


def environment(route_id='a', *, rainfall=0, wbgt=26, pm25=0, psi=400, wind_speed=2,
                category='Low', distance=.5, observed_at=NOW, **updates):
    values = dict(rainfall=rainfall, wbgt=wbgt, pm25=pm25, psi=psi, wind_speed=wind_speed,
                  heat_stress_level=None)
    metrics = []
    for metric, value in values.items():
        overrides = value if isinstance(value, dict) else updates.get(metric, {})
        if isinstance(value, dict):
            value = {'rainfall': 0, 'wbgt': 26, 'pm25': 0, 'psi': 400, 'wind_speed': 2}.get(metric)
        unit, window, source = METRIC_SPECS[metric]
        regional = metric in {'pm25', 'psi'}
        m = RouteMetric(route_id=route_id, metric=metric, value=value,
                        category_value=category if metric == 'heat_stress_level' else None,
                        unit=unit, aggregation_window=window, source=source, location_id='south' if regional else 'S1',
                        source_kind='live', delivery='live', state='fresh',
                        match_method='configured_source_region_v1' if regional else 'nearest_available_station_start_point_v1',
                        station_distance_km=None if regional else distance,
                        observed_at=observed_at, fetched_at=observed_at, as_of=NOW)
        metrics.append(m.model_copy(update=overrides))
    return RouteEnvironment(route_id=route_id, as_of=NOW, metrics=metrics)


def assess(config, env, as_of=NOW):
    return EnvironmentalRiskAssessor(config).assess([env], as_of=as_of)[0]


@pytest.mark.parametrize('value,expected', [(None, None), (-1, 0), (0, 0), (.5, 10), (1, 20), (3, 40), (5, 60), (10, 100), (20, 100)])
def test_normalization_boundaries(config, value, expected):
    assert normalize(value, config.risk.rainfall) == expected


def test_zero_is_not_missing_and_no_renormalization(config):
    zero = assess(config, environment())
    assert zero.risk_score == 0 and zero.eligibility == 'eligible'
    unknown = assess(config, environment(rainfall=None))
    assert unknown.risk_score is None and unknown.eligibility == 'unknown'
    assert unknown.risk_components['rainfall'].score is None
    assert unknown.risk_data_quality.completeness == .75
    assert unknown.risk_status == 'incomplete'


@pytest.mark.parametrize('wbgt,category,score', [(26, 'Low', 0), (31, 'Moderate', 50), (33, 'High', 80), (35, 'High', 100)])
def test_wbgt_numeric_and_category_boundaries(config, wbgt, category, score):
    risk = assess(config, environment(wbgt=wbgt, category=category))
    heat = risk.risk_components['heat']
    assert heat.score == score and heat.category == category and heat.metric == 'wbgt'
    # Category metadata never adds a second heat contribution.
    different_metadata = assess(config, environment(wbgt=wbgt, category='High'))
    assert different_metadata.risk_score == risk.risk_score


@pytest.mark.parametrize('category,score', [('Low', 20), ('Moderate', 60), ('High', 90)])
def test_category_fallback(config, category, score):
    risk = assess(config, environment(wbgt=None, category=category))
    assert risk.risk_components['heat'].score == score
    assert risk.risk_components['heat'].metric == 'heat_stress_level'
    assert risk.eligibility == 'caution'


def test_air_precedence_windows_and_stale_fallback(config):
    a = assess(config, environment(pm25=55, psi=0))
    b = assess(config, environment(pm25=55, psi=400))
    assert a.risk_score == b.risk_score
    assert a.risk_components['air_quality'].aggregation_window == 'PT1H'
    fallback = assess(config, environment(pm25=None, psi=100))
    assert fallback.risk_components['air_quality'].score == 35
    assert fallback.risk_components['air_quality'].aggregation_window == 'PT24H'
    old = NOW - timedelta(hours=3)
    stale = assess(config, environment(pm25={'observed_at': old, 'fetched_at': old}))
    assert stale.risk_components['air_quality'].metric == 'psi'


def test_freshness_recomputed_not_persisted_state(config):
    env = environment()
    stale = assess(config, env, NOW + timedelta(hours=3))
    assert stale.risk_score is None and stale.eligibility == 'unknown'
    assert stale.risk_components['rainfall'].freshness == 'stale'
    assert stale.risk_components['heat'].freshness == 'stale'
    assert stale.risk_components['air_quality'].freshness == 'stale'
    fresh = assess(config, environment(rainfall={'state': 'stale'}))
    assert fresh.risk_components['rainfall'].score == 0
    future = assess(config, env, NOW - timedelta(seconds=1))
    assert future.risk_components['rainfall'].freshness == 'unavailable_as_of'
    assert future.risk_score is None
    with pytest.raises(ValueError, match='timezone'):
        assess(config, env, NOW.replace(tzinfo=None))


@pytest.mark.parametrize('distance,quality,complete', [(0, 'high', True), (1, 'high', True), (1.01, 'moderate', True), (3, 'moderate', True), (3.01, 'low', True), (5, 'low', True), (5.01, 'very_low', False), (None, 'unknown', False)])
def test_spatial_bands(config, distance, quality, complete):
    # Preserve the original strict-policy coverage; approximation has separate tests.
    config.risk.allow_approximate_station_estimates = False
    risk = assess(config, environment(distance=distance))
    assert risk.risk_components['rainfall'].spatial_quality == quality
    assert (risk.risk_score is not None) == complete
    assert risk.risk_components['air_quality'].spatial_quality == 'regional'


def test_neutral_wind_is_not_missing_wind(config):
    assert assess(config, environment(wind_speed=15)).risk_components['wind'].score == 0
    assert assess(config, environment(wind_speed=None)).risk_score is None
    config.risk.wind_scoring_enabled = True
    assert assess(config, environment(wind_speed=8)).risk_components['wind'].score == 0
    assert assess(config, environment(wind_speed=20)).risk_components['wind'].score == 100


def test_missing_heat_and_air_and_invalid_contract(config):
    missing = assess(config, environment(wbgt=None, category=None, pm25=None, psi=None))
    assert missing.risk_score is None and missing.risk_data_quality.completeness == .5
    invalid = assess(config, environment(rainfall={'aggregation_window': 'PT1H'}))
    assert invalid.risk_score is None


def test_policy_disabled_supported_block_and_partial_block(config):
    high = environment(rainfall=10, wbgt=35, pm25=350)
    assert assess(config, high).eligibility == 'caution'
    rule = BlockingRule(metric='wbgt', threshold=33, reason='Synthetic test policy only', policy_source='test://fixture')
    config.risk.blocking_rules = [rule]
    assert assess(config, high).eligibility == 'caution'
    config.risk.blocking_rules = [rule.model_copy(update={'enabled': True})]
    assert assess(config, high).eligibility == 'blocked'
    partial = assess(config, environment(wbgt=35, rainfall=None))
    assert partial.eligibility == 'blocked' and partial.risk_score is None
    stale = assess(config, high, NOW + timedelta(hours=3))
    assert stale.eligibility == 'unknown'
    with pytest.raises(ValidationError):
        BlockingRule(enabled=True, metric='wbgt', threshold=33)


def test_config_validation():
    with pytest.raises(ValidationError):
        Curve(points=[(1, 50), (0, 100)])
    with pytest.raises(ValidationError):
        RiskConfig(weights=dict(rainfall=1))
    with pytest.raises(ValidationError):
        RankingConfig(weights=dict(environment=.5, distance=.3, accessibility=.2, difficulty=.2))


def route(route_id, distance):
    return Route(route_id=route_id, name=route_id, kind='loop', distance_km=distance,
                 status='candidate_requires_visual_review', attribution='synthetic test',
                 geometry=LineString(coordinates=[(103.85, 1.28), (103.86, 1.29)]))


def rank(config, envs, routes=None, preferences=None, difficulties=None):
    routes = routes or [route(e.route_id, 4) for e in envs]
    preferences = preferences or Preferences()
    conditions = [Conditions(route_id=r.route_id, rainfall_mm=0, station_ids=[], source='unavailable', quality='missing') for r in routes]
    predictions = [Prediction(route_id=r.route_id, horizon_min=30, generated_at=NOW, source='model_not_connected', is_mock=False, status='unavailable') for r in routes]
    baseline = BaselineRecommender().rank(routes, conditions, predictions, preferences)
    risks = EnvironmentalRiskAssessor(config).assess(envs, as_of=NOW)
    result = RiskAwareRanking(config.ranking).rank(baseline, risks, routes, preferences, difficulties or {r.route_id: 3 for r in routes})
    return baseline, result


def test_risk_changes_ranking_and_preserves_baseline_score(config):
    baseline, new = rank(config, [environment('a', rainfall=10, wbgt=35, pm25=350), environment('b')])
    assert [r.route_id for r in baseline] == ['a', 'b']
    assert [r.route_id for r in new] == ['b', 'a']
    assert new[0].recommendation_score == 92.5 and new[1].recommendation_score == 49.75
    assert all(r.score == 100 for r in new)
    assert {r.route_id for r in new} == {r.route_id for r in baseline}


def test_unknown_fallback_no_complete_score_and_deterministic(config):
    envs = [environment('b', rainfall=None), environment('a', rainfall=None)]
    _, new = rank(config, envs)
    _, again = rank(config, list(reversed(envs)))
    assert [r.route_id for r in new] == [r.route_id for r in again] == ['a', 'b']
    assert all(r.recommendation_score is None and r.ranking_method == 'legacy_non_environmental' for r in new)
    _, mixed = rank(config, [environment('unknown', rainfall=None), environment('known', rainfall=10, wbgt=35, pm25=350)])
    assert [r.route_id for r in mixed] == ['known', 'unknown']


def test_distance_mismatch_no_invented_access_and_personal_matching(config):
    _, new = rank(config, [environment('long')], routes=[route('long', 4)], preferences=Preferences(target_distance_km=1.2))
    rec = new[0]
    assert rec.distance_difference_km == 2.8
    assert rec.relative_distance_difference == pytest.approx(2.333333, abs=1e-6)
    assert rec.distance_match_warning and rec.recommendation_components['distance'] == 0
    assert rec.access_distance_km is None and rec.recommendation_components['accessibility'] == 50
    _, personal = rank(config, [environment('a'), environment('b')], difficulties={'a': 1, 'b': 3})
    assert [r.route_id for r in personal] == ['b', 'a']


def test_access_filter_and_blocks_cannot_be_overridden(config):
    prefs = Preferences(location={'lon': 0, 'lat': 0}, max_access_distance_km=1)
    assert rank(config, [environment()], preferences=prefs)[1] == []
    config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=33,
                                             reason='Synthetic policy', policy_source='test://fixture')]
    _, new = rank(config, [environment('blocked', wbgt=35), environment('other', rainfall=None)], difficulties={'blocked': 3, 'other': 1})
    assert [r.route_id for r in new] == ['other', 'blocked']
    assert new[-1].recommendation_score is None


def test_api_backward_compatibility_forecast_and_personalization(tmp_path):
    from fastapi.testclient import TestClient
    from outdoorwise.api.app import create_app
    from outdoorwise.personalization.router import get_service
    shutil.copytree(ROOT / 'data/catalog', tmp_path / 'catalog')
    app = create_app(Settings(data_root=tmp_path, data_mode='live'))
    pipeline = app.state.pipeline
    envs = [environment(r.route_id, observed_at=datetime.now(timezone.utc)) for r in pipeline.repository.load_routes()]
    pipeline.environment_service.refresh_latest = lambda: envs
    with TestClient(app) as client:
        old_fields = {'route_id', 'score', 'access_distance_km', 'distance_difference_km', 'reasons'}
        response = client.post('/api/recommendations', json={'target_distance_km': 1.2, 'duration_min': 45, 'horizon_min': 60})
        assert response.status_code == 200
        run = response.json()
        assert old_fields <= set(run['recommendations'][0])
        assert len(run['routes']) == 12 and len(run['risks']) == 12
        assert run['preferences']['duration_min'] == 45
        assert all(p['prediction_status'] == 'forecast_unavailable' and p['rain_probability'] is None for p in run['predictions'])
        assert all(r['risk_assessment_mode'] == 'current_observation' for r in run['risks'])
        assert all(r['recommendation_score'] is not None for r in run['recommendations'])
        assert client.post('/api/me/recommendations', json={'target_difficulty': 3}).status_code == 401
        assert client.post('/api/auth/register', json={'username': 'risk_runner', 'password': 'password123'}).status_code == 201
        # Exercise existing personal calibration provider without changing account storage.
        service = app.dependency_overrides[get_service]()
        original = service.get_personalized_difficulty
        def difficulty(user_id, route, env):
            result = original(user_id, route, env)
            result['personalized_predicted_difficulty'] = 3 if route.route_id == 'marina_bay' else 5
            return result
        service.get_personalized_difficulty = difficulty
        app.dependency_overrides[get_service] = lambda: service
        personal = client.post('/api/me/recommendations', json={'target_difficulty': 3}).json()
        assert set(personal) == {'run', 'target_difficulty', 'recommendations'}
        assert personal['recommendations'][0]['route_id'] == 'marina_bay'
        assert personal['run']['recommendations'][0]['recommendation_components']['difficulty'] == 100
        assert {r['route_id'] for r in personal['recommendations']} == {r['route_id'] for r in personal['run']['recommendations']}
        assert client.get('/api/me/running-profile').status_code == 200
        assert client.get('/api/routes/marina_bay/export.gpx').status_code == 200


def test_configured_weights_and_freshness_boundary(config):
    env = environment(rainfall=5, wbgt=31, pm25=55)
    risk = assess(config, env)
    assert risk.risk_score == pytest.approx(.35 * 60 + .35 * 50 + .25 * 25)
    config.risk.weights = dict(rainfall=1, heat=0, air_quality=0, wind=0)
    assert assess(config, env).risk_score == 60
    at_limit = assess(config, env, NOW + timedelta(seconds=900))
    assert at_limit.risk_components['rainfall'].freshness == 'fresh'
    past_limit = assess(config, env, NOW + timedelta(seconds=901))
    assert past_limit.risk_components['rainfall'].score is None


@pytest.mark.parametrize('updates', [dict(fetched_at=None), dict(fetched_at=NOW+timedelta(seconds=1)), dict(observed_at=None), dict(source_updated_at=NOW+timedelta(seconds=1)), dict(station_distance_km=-1)])
def test_unavailable_or_invalid_evidence_never_scores_zero(config, updates):
    risk = assess(config, environment(rainfall=updates))
    assert risk.risk_components['rainfall'].score is None and risk.risk_score is None


def test_personal_reranking_does_not_override_policy_or_weighted_score(config):
    from outdoorwise.personalization.ranking import rank_candidates
    config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=33,
                                             reason='Synthetic only', policy_source='test://policy')]
    _, recs = rank(config, [environment('blocked', wbgt=35), environment('good'), environment('unknown', rainfall=None)])
    predictions = [dict(route_id=r.route_id, generic_predicted_difficulty=3,
                        personalized_predicted_difficulty=3 if r.route_id == 'blocked' else 5,
                        confidence='high') for r in recs]
    ranked = rank_candidates(recs, predictions, 3)
    assert [r['route_id'] for r in ranked] == ['good', 'unknown', 'blocked']


def test_api_unknown_discovery_no_match_and_all_blocked(tmp_path):
    from fastapi.testclient import TestClient
    from outdoorwise.api.app import create_app
    shutil.copytree(ROOT / 'data/catalog', tmp_path / 'catalog')
    app = create_app(Settings(data_root=tmp_path, data_mode='live'))
    pipeline = app.state.pipeline
    with TestClient(app) as client:
        unknown = client.post('/api/recommendations', json={'target_distance_km': .1}).json()
        assert len(unknown['recommendations']) == 12
        assert all(r['recommendation_score'] is None and r['eligibility'] == 'unknown' for r in unknown['recommendations'])
        assert any('No candidate reasonably matches' in w for w in unknown['warnings'])
        assert any('non-environmental criteria' in w for w in unknown['warnings'])
        config = pipeline.config
        config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=33,
                                                 reason='Synthetic policy only', policy_source='test://fixture')]
        envs = [environment(r.route_id, wbgt=35, observed_at=datetime.now(timezone.utc)) for r in pipeline.repository.load_routes()]
        pipeline.environment_service.refresh_latest = lambda: envs
        blocked = client.post('/api/recommendations', json={}).json()
        assert blocked['recommendations'] == []
        assert len(blocked['routes']) == 12 and all(r['eligibility'] == 'blocked' for r in blocked['risks'])
        client.post('/api/auth/register', json={'username': 'blocked_runner', 'password': 'password123'})
        personal = client.post('/api/me/recommendations', json={'target_difficulty': 3}).json()
        assert personal['recommendations'] == [] and personal['run']['recommendations'] == []


@pytest.mark.parametrize('distance,scored', [(5.01, True), (5.193, True), (8, True), (15, True), (15.001, False), (None, False)])
def test_approximate_mapping_availability_is_separate_from_confidence(config, distance, scored):
    # East Coast's recorded Mapping V1 wind distance is 5.193 km.
    risk = assess(config, environment('east_coast', wind_speed={'station_distance_km': distance}))
    wind = risk.risk_components['wind']
    assert (risk.risk_score is not None) == scored
    if scored:
        assert wind.estimate_status == 'approximate' and wind.spatial_quality == 'very_low'
        assert risk.risk_score == 0 and risk.risk_level == 'low'
        assert risk.risk_data_quality.confidence == 'very_low' and risk.eligibility == 'caution'
        assert risk.risk_data_quality.scored_components == 4
        assert risk.risk_data_quality.reliable_components == 3
        assert any('not a measurement along this route' in w for w in wind.warnings)
    else:
        assert wind.score is None and wind.estimate_status == 'unavailable'
        assert risk.risk_data_quality.confidence == 'unknown'


@pytest.mark.parametrize('updates,label', [
    ({'observed_at': NOW-timedelta(seconds=901), 'fetched_at': NOW-timedelta(seconds=901)}, 'stale'),
    ({'value': None}, 'missing'),
    ({'fetched_at': NOW+timedelta(seconds=1)}, 'unavailable_as_of'),
])
def test_distant_estimate_does_not_override_temporal_availability(config, updates, label):
    risk = assess(config, environment('east_coast', wind_speed={'station_distance_km': 5.193, **updates}))
    wind = risk.risk_components['wind']
    assert wind.freshness == label and wind.score is None
    assert wind.estimate_status == 'unavailable' and risk.risk_score is None
    assert risk.eligibility == 'unknown'


def test_low_confidence_caution_is_not_automatically_demoted(config):
    _, recs = rank(config, [environment('east_coast', distance=5.193),
                           environment('west_coast', wbgt=31, distance=.641)])
    # Low-confidence approximate score is useful, but never asserts route-wide safety.
    assert recs[0].route_id == 'east_coast' and recs[0].eligibility == 'caution'
    assert recs[1].route_id == 'west_coast' and recs[1].eligibility == 'eligible'
    assert recs[0].recommendation_score > recs[1].recommendation_score
    assert recs[0].risk_confidence == 'very_low'
    assert recs[0].score == recs[1].score == 100
    assert recs[0].final_rank == 1 and recs[1].final_rank == 2


def test_blocking_approximate_evidence_requires_policy_authorization(config):
    rule = BlockingRule(enabled=True, metric='wbgt', threshold=33,
                        reason='Synthetic test only', policy_source='test://fixture')
    config.risk.blocking_rules = [rule]
    env = environment('east_coast', wbgt=35, distance=5.193)
    caution = assess(config, env)
    assert caution.eligibility == 'caution' and any('does not authorize approximate' in w for w in caution.risk_warnings)
    config.risk.blocking_rules = [rule.model_copy(update={'allow_approximate_estimates': True})]
    assert assess(config, env).eligibility == 'blocked'
    _, recs = rank(config, [env, environment('west_coast', rainfall=None)])
    assert [r.route_id for r in recs] == ['west_coast', 'east_coast']
    assert recs[-1].recommendation_score is None


@pytest.mark.parametrize('unknown', [False, True])
def test_personal_endpoint_and_run_have_identical_final_order_and_rank(tmp_path, unknown):
    from fastapi.testclient import TestClient
    from outdoorwise.api.app import create_app
    from outdoorwise.personalization.router import get_service
    shutil.copytree(ROOT / 'data/catalog', tmp_path / 'catalog')
    app = create_app(Settings(data_root=tmp_path, data_mode='live'))
    pipeline = app.state.pipeline
    now = datetime.now(timezone.utc)
    routes = pipeline.repository.load_routes()
    assert len(routes) == 12
    envs = [environment(r.route_id, rainfall=None, observed_at=now) for r in routes]
    if not unknown:
        envs = [environment('east_coast', wind_speed={'station_distance_km': 5.193}, observed_at=now),
                environment('west_coast', rainfall=10, wbgt=35, pm25=350,
                            wind_speed={'station_distance_km': 1.816}, observed_at=now)] + [e for e in envs if e.route_id not in {'east_coast', 'west_coast'}]
    pipeline.environment_service.refresh_latest = lambda: envs
    service = app.dependency_overrides[get_service]()
    def personal_difficulty(user_id, route, env):
        difficulty = 3 if route.route_id == 'west_coast' else 5
        return dict(route_id=route.route_id, generic_predicted_difficulty=3,
                    personalized_predicted_difficulty=difficulty, confidence='high')
    service.get_personalized_difficulty = personal_difficulty
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        assert client.post('/api/auth/register', json={'username': 'hardening_runner', 'password': 'password123'}).status_code == 201
        response = client.post('/api/me/recommendations', json={'target_distance_km': 4, 'target_difficulty': 3})
        assert response.status_code == 200
        data = response.json()
        outer, inner = data['recommendations'], data['run']['recommendations']
        assert len(outer) == len(inner) == 12
        assert [r['route_id'] for r in outer] == [r['route_id'] for r in inner]
        for index, (personal, rec) in enumerate(zip(outer, inner), 1):
            assert personal['personalized_rank'] == personal['final_rank'] == rec['final_rank'] == index
            assert personal['original_base_rank'] == rec['original_base_rank']
            assert personal['base_recommendation_score'] == rec['score']
            assert personal['recommendation_score'] == rec['recommendation_score']
        # A perfect difficulty match cannot replace a better complete weighted score.
        if not unknown:
            assert [r['route_id'] for r in outer[:2]] == ['east_coast', 'west_coast']
            assert outer[0]['difficulty_mismatch'] > outer[1]['difficulty_mismatch']
            assert outer[0]['recommendation_score'] > outer[1]['recommendation_score']
            assert inner[0]['recommendation_components']['difficulty'] == 50
            assert inner[0]['risk_confidence'] == 'very_low'
            pipeline.config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=33,
                                                              reason='Synthetic policy', policy_source='test://fixture')]
            blocked = client.post('/api/me/recommendations', json={'target_distance_km': 4, 'target_difficulty': 3}).json()
            assert len(blocked['recommendations']) == 11
            assert 'west_coast' not in {r['route_id'] for r in blocked['recommendations']}
            assert [r['final_rank'] for r in blocked['run']['recommendations']] == list(range(1, 12))
            assert blocked['recommendations'][0]['route_id'] == 'east_coast'
            # Restore the initial persisted result for the audit consistency assertion.
            pipeline.config.risk.blocking_rules = []
            client.post('/api/me/recommendations', json={'target_distance_km': 4, 'target_difficulty': 3})
        else:
            assert outer[0]['route_id'] == 'west_coast'
            assert all(r['recommendation_score'] is None for r in inner)
            assert all(r['ranking_method'] == 'personalized_non_environmental' for r in inner)
        # Persisted audit order must agree with the returned final order too.
        import json
        saved = json.loads((tmp_path/'runtime/latest_run.json').read_text())
        assert [r['route_id'] for r in saved['recommendations']] == [r['route_id'] for r in inner]
