"""Departure integration tests. Research components and risk policy stay read-only."""
import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.api.forecast_ranking import load_snapshot
from outdoorwise.api.historical_departure import assess_departure, full_run_coverage
from outdoorwise.api.time_selection import REPLAY_TIME, historical_forecast
from outdoorwise.config import ROOT, Settings, load_environment_config
from outdoorwise.contracts.environment import timestamp
from outdoorwise.contracts.risk import BlockingRule
from outdoorwise.modules.risk import EnvironmentalRiskAssessor
from outdoorwise.services.route_environment import RouteEnvironmentService
from outdoorwise.storage.repository import FileRepository


@pytest.fixture(scope='module')
def context():
    routes = FileRepository.load_routes(SimpleNamespace(root=ROOT/'data'))
    snapshot = load_snapshot(str(ROOT), REPLAY_TIME)
    class Reader:
        def load_routes(self): return routes
        def environment_snapshot(self, *args): return (*snapshot, [])
    config = load_environment_config(ROOT/'config/environment.toml')
    origin = timestamp(REPLAY_TIME)
    environments = RouteEnvironmentService(Reader(), config, 'live').get_all(origin)
    risks = EnvironmentalRiskAssessor(config).assess(environments, origin)
    return config, origin, {row.route_id: row for row in environments}, {row.route_id: row for row in risks}


def test_now_exactly_reuses_production_risk_and_policy(context):
    config, origin, environments, risks = context
    for route_id, env in environments.items():
        result = assess_departure(env, risks[route_id], {}, config, origin, 0)
        assert result['risk'] == risks[route_id].model_dump(mode='json')
        assert result['scope'] == 'departure_only'
        assert result['assessment_type'] == 'historical_observation'
    assert risks['marina_bay'].risk_score == 17.49
    assert all(risk.risk_score is not None for risk in risks.values())


@pytest.mark.parametrize('delay', [30, 60])
def test_delayed_native_wbgt_target_is_mapped_without_other_carry_forward(context, delay):
    config, origin, envs, risks = context
    native = historical_forecast('marina_bay', 0, delay)
    before = json.dumps(native, sort_keys=True)
    result = assess_departure(envs['marina_bay'], risks['marina_bay'], native, config, origin, delay)
    wbgt = result['inputs']['wbgt']
    assert wbgt['value'] == 26.3 and wbgt['method'] == 'persistence'
    assert timestamp(wbgt['target_timestamp']) == origin+timedelta(minutes=delay)
    assert wbgt['location_id'] == 'S144' and wbgt['unit'] == 'degC'
    assert result['risk']['risk_components']['heat']['score'] == pytest.approx(3.0)
    assert result['risk']['risk_score'] is None and result['risk']['eligibility'] == 'unknown'
    assert all(result['inputs'][metric]['value'] is None for metric in ('rainfall', 'pm25', 'wind_speed', 'psi', 'heat_stress_level'))
    assert 'No exact native' in result['inputs']['pm25']['reason']
    assert json.dumps(native, sort_keys=True) == before


@pytest.mark.parametrize('mutation', ['unit', 'station', 'future_input', 'source_timestamp', 'missing_value', 'unsupported_horizon', 'missing_model'])
def test_native_target_requires_semantic_and_temporal_compatibility(context, mutation):
    from copy import deepcopy
    config, origin, envs, risks = context
    native = deepcopy(historical_forecast('marina_bay', 0, 30))
    series = native['metrics']['wbgt']
    block = next(row for row in series['blocks'] if timestamp(row['valid_to']) == origin+timedelta(minutes=30))
    if mutation == 'unit': series['unit'] = 'fahrenheit'
    if mutation == 'station': native['sources']['wbgt']['station_id'] = 'another-station'
    if mutation == 'future_input': block['input_provenance'][0]['available_at'] = (origin+timedelta(minutes=1)).isoformat()
    if mutation == 'source_timestamp': block['input_provenance'][0]['observed_at'] = (origin-timedelta(days=1)).isoformat()
    if mutation == 'missing_value': block['value'] = None
    if mutation == 'unsupported_horizon': series['model_origin'] = (origin-timedelta(minutes=1)).isoformat()
    if mutation == 'missing_model': block.update(method='frozen_experimental_linear', model_version='unavailable')
    result = assess_departure(envs['marina_bay'], risks['marina_bay'], native, config, origin, 30)
    assert result['inputs']['wbgt']['value'] is None
    assert result['risk']['risk_components']['heat']['score'] is None
    assert result['risk']['risk_score'] is None


def test_departure_point_does_not_establish_full_run_coverage(context):
    from outdoorwise.api.historical_evidence import describe_forecast
    config, origin, envs, risks = context
    for delay, expected in [(0, 'partial'), (30, 'unavailable'), (60, 'unavailable')]:
        raw = historical_forecast('marina_bay', delay, 30)
        full = full_run_coverage(describe_forecast(raw))
        assert full['status'] == expected and full['risk_score'] is None
    now = assess_departure(envs['marina_bay'], risks['marina_bay'], {}, config, origin, 0)
    assert now['risk']['risk_score'] == 17.49


def test_missing_wind_remains_unknown_even_with_neutral_wind_scoring(context):
    config, origin, envs, _ = context
    env = envs['marina_bay'].model_copy(deep=True)
    next(metric for metric in env.metrics if metric.metric == 'wind_speed').value = None
    risk = EnvironmentalRiskAssessor(config).assess([env], origin)[0]
    assert not config.risk.wind_scoring_enabled
    assert assess_departure(env, risk, {}, config, origin, 0)['risk']['risk_score'] is None


def test_inherited_blocking_policy_applies_to_exact_native_forecast(context):
    config, origin, envs, risks = context
    config = config.model_copy(deep=True)
    config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=26,
        reason='Synthetic threshold for testing', policy_source='test-only')]
    result = assess_departure(envs['marina_bay'], risks['marina_bay'],
        historical_forecast('marina_bay', 0, 30), config, origin, 30)
    assert result['risk']['eligibility'] == 'blocked'
    assert result['risk']['risk_score'] is None  # other required components are still absent


def protected_hashes():
    paths = [p for folder in ('prediction', 'data') for p in (ROOT/folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT/'docs/forecast_evaluation.json', ROOT/'docs/PREDICTION_MODELS.md']
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_http_never_fits_models_or_mutates_protected_research(tmp_path, monkeypatch):
    import shutil
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.preprocessing import StandardScaler
    def forbidden(*args, **kwargs): raise AssertionError('No request-time fitting is authorized')
    for cls in (LinearRegression, LogisticRegression, StandardScaler):
        monkeypatch.setattr(cls, 'fit', forbidden)
    shutil.copytree(ROOT/'data/catalog', tmp_path/'catalog')
    before = protected_hashes()
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode='live', app_mode='historical'))) as client:
        for delay in (0, 30, 60):
            response = client.post('/api/route-recommendations', json={'start_delay_min': delay})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data['recommendation_basis'] == ('historical_observation_risk' if delay == 0 else 'unknown_risk_fallback')
            if delay == 0:
                assert all(row['recommendation_score'] is not None for row in data['recommendations'])
            else:
                assert all(row['recommendation_score'] is None for row in data['recommendations'])
    assert protected_hashes() == before
