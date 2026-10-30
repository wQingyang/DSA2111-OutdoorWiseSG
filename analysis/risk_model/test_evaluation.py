"""Independent analytic expectations and evaluation harness regressions."""
from datetime import timedelta
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from analysis.risk_model.analyze import (
    ArchivedReader, NOW, ROOT, assess, boundary_tests, fixture, rank, sensitivity,
)
from outdoorwise.config import load_environment_config
from outdoorwise.contracts.environment import EnvironmentObservation
from outdoorwise.contracts.models import Route, LineString


@pytest.fixture
def config():
    return load_environment_config(ROOT/'config/environment.toml')


def test_independent_hand_calculation_and_missing_zero_weight(config):
    # At rainfall=3, component=40; WBGT=32 ->65; PM2.5=55 ->25.
    risk = assess(config, fixture(values=dict(rainfall=3, wbgt=32, pm25=55)))
    assert risk.risk_score == 43
    assert risk.eligibility == 'caution'
    config.risk.weights = dict(rainfall=.4, heat=.35, air_quality=.25, wind=0)
    assert assess(config, fixture(values={'wind_speed': None})).risk_score is None


def test_policy_expectations_and_sensitivity_branches(config):
    cases = boundary_tests(config)
    assert len(cases) >= 70
    assert all(c['passed'] for c in cases), [c for c in cases if not c['passed']]
    data = sensitivity(config)
    ignored = [r for r in data if r['metric'] == 'psi' and r['branch'] == 'pm25_preferred']
    assert len(ignored) > 100 and {r['total_risk'] for r in ignored} == {0}
    assert max(r['total_risk'] for r in data if r['metric'] == 'rainfall') == 35
    assert max(r['total_risk'] for r in data if r['metric'] == 'psi') == 25


def test_archived_availability_no_future_revision_or_fetch():
    reader = ArchivedReader.__new__(ArchivedReader)
    reader.locations = []
    base = EnvironmentObservation(source='nea_rainfall', location_id='fixture',
        metric='rainfall', value=1, unit='mm', aggregation_window='PT5M',
        observed_at=NOW-timedelta(minutes=5), fetched_at=NOW-timedelta(minutes=4),
        first_fetched_at=NOW-timedelta(minutes=4))
    future = base.model_copy(update=dict(revision=2, value=10, first_fetched_at=NOW+timedelta(minutes=1), fetched_at=NOW+timedelta(minutes=1)))
    reader.versions = [base, future]
    reader.current = [future]
    _, observations, _ = reader.environment_snapshot('live', NOW)
    assert len(observations) == 1 and observations[0].value == 1
    _, later, _ = reader.environment_snapshot('live', NOW+timedelta(minutes=2))
    assert len(later) == 1 and later[0].value == 10
    # Compare the production pure method using an in-memory storage port; no constructor.
    from outdoorwise.storage.repository import FileRepository
    port = SimpleNamespace(
        _guard=nullcontext,
        _read=lambda name: [],
        _observation_rows=lambda versions=False: [
            o.model_dump(mode='json') for o in (reader.versions if versions else reader.current)])
    for time in [NOW, NOW+timedelta(minutes=2)]:
        expected = FileRepository.environment_snapshot(port, 'live', time)
        actual = reader.environment_snapshot('live', time)
        assert actual == expected


def test_baselines_keep_unknown_group_after_known_and_deterministic_ties(config):
    routes = [Route(route_id=r, name=r, kind='loop', distance_km=5,
        status='candidate_requires_visual_review', attribution='fixture',
        geometry=LineString(coordinates=[(103.8, 1.3), (103.81, 1.31)])) for r in ('b', 'a', 'unknown')]
    envs = [fixture(r.route_id, values={'rainfall': None} if r.route_id == 'unknown' else {}) for r in routes]
    for method in ('distance', 'no_environment', 'full'):
        ranked, _, _ = rank(config, routes, envs, NOW, method)
        assert [r.route_id for r in ranked] == ['a', 'b', 'unknown']
        assert ranked[-1].recommendation_score is None
    from outdoorwise.contracts.risk import BlockingRule
    config.risk.blocking_rules = [BlockingRule(enabled=True, metric='rainfall', threshold=1,
        reason='test only', policy_source='analysis://fixture')]
    envs[0] = fixture('b', values={'rainfall': 1})
    for method in ('distance', 'no_environment', 'full'):
        ranked, _, _ = rank(config, routes, envs, NOW, method)
        assert [r.route_id for r in ranked] == ['a', 'unknown']


@pytest.mark.parametrize('unusable', [
    {'value': None}, {'value': float('nan')},
    {'observed_at': NOW-timedelta(seconds=7201)},
    {'fetched_at': NOW+timedelta(seconds=1)},
    {'source_updated_at': NOW+timedelta(seconds=1)},
    {'observed_at': None}, {'fetched_at': None},
    {'unit': 'wrong'}, {'location_id': None}, {'match_method': 'unsupported'},
])
def test_psi_fallback_requires_usable_pm25_not_merely_present(config, unusable):
    risk = assess(config, fixture(values={'pm25': 55, 'psi': 100}, overrides={'pm25': unusable}))
    assert risk.risk_components['air_quality'].metric == 'psi'
    assert risk.risk_components['air_quality'].score == 35
    assert risk.risk_score == 8.75 and risk.eligibility == 'caution'
    assert risk.risk_components['heat'].score == risk.risk_components['rainfall'].score == 0


def test_both_air_inputs_unknown_stays_unknown_and_nonzero_pm25_is_not_flat_zero(config):
    for psi in (0, 100, 500):
        risk = assess(config, fixture(values={'pm25': 55, 'psi': psi}))
        assert risk.risk_components['air_quality'].metric == 'pm25'
        assert risk.risk_components['air_quality'].score == 25
        assert risk.risk_score == 6.25  # PSI-independent, not universally zero.
    for overrides in ({}, {name: {'observed_at': NOW-timedelta(hours=3)} for name in ('pm25', 'psi')}):
        env = fixture(values=dict(pm25=None, psi=None)) if not overrides else fixture(overrides=overrides)
        risk = assess(config, env)
        assert risk.risk_components['air_quality'].score is None
        assert risk.risk_score is None and risk.eligibility == 'unknown'


def test_every_saved_sweep_total_matches_components_and_plot_ignored_branch(config):
    for row in sensitivity(config):
        expected = round(.35*row['rainfall_risk']+.35*row['heat_risk']+.25*row['air_risk']+.05*row['wind_risk'], 2)
        assert row['total_risk'] == expected
        if row['branch'] == 'pm25_preferred':
            assert row['selected_metric'] == 'pm25' and row['air_risk'] == row['total_risk'] == 0
