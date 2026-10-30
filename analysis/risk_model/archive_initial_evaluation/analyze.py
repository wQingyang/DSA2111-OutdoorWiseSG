"""Offline rule evaluation. Never initialize FileRepository or application startup."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', tempfile.mkdtemp(prefix='risk-mpl-'))
os.environ.setdefault('XDG_CACHE_HOME', tempfile.mkdtemp(prefix='risk-cache-'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from outdoorwise.config import load_environment_config
from outdoorwise.contracts.environment import (
    METRIC_SPECS, EnvironmentObservation, Location, RouteEnvironment, RouteMetric,
)
from outdoorwise.contracts.models import Conditions, Prediction, Preferences
from outdoorwise.contracts.risk import BlockingRule, RankingConfig
from outdoorwise.difficulty.service import GenericDifficultyEstimator
from outdoorwise.modules.recommender import BaselineRecommender
from outdoorwise.modules.risk import EnvironmentalRiskAssessor
from outdoorwise.modules.risk_ranking import RiskAwareRanking
from outdoorwise.services.route_environment import RouteEnvironmentService
from outdoorwise.storage.repository import FileRepository, csv_datetime, typed

HERE = Path(__file__).resolve().parent
SGT = ZoneInfo('Asia/Singapore')
NOW = datetime(2026, 10, 15, 12, tzinfo=SGT)
METRICS = ('rainfall', 'wbgt', 'pm25', 'psi', 'wind_speed', 'heat_stress_level')
COLORS = ('#0072B2', '#D55E00', '#009E73', '#8255A5')


def rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, data):
    assert data, path
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def hashes(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths))}


def fixture(route_id='marina_bay', values=None, overrides=None):
    """Controlled interface fixture, not an observed route-wide measurement."""
    values = dict(rainfall=0, wbgt=26, pm25=0, psi=0, wind_speed=2,
                  heat_stress_level='Low') | (values or {})
    metrics = []
    for name in METRICS:
        unit, window, source = METRIC_SPECS[name]
        regional = name in {'pm25', 'psi'}
        category = name == 'heat_stress_level'
        metric = RouteMetric(
            route_id=route_id, metric=name, value=None if category else values[name],
            category_value=values[name] if category else None, unit=unit,
            aggregation_window=window, source=source, source_kind='live',
            delivery='live', state='fresh', location_id='south' if regional else 'fixture',
            match_method='configured_source_region_v1' if regional else 'nearest_available_station_start_point_v1',
            station_distance_km=None if regional else .5,
            observed_at=NOW, fetched_at=NOW, as_of=NOW)
        metrics.append(metric.model_copy(update=(overrides or {}).get(name, {})))
    return RouteEnvironment(route_id=route_id, as_of=NOW, metrics=metrics)


def assess(config, env):
    return EnvironmentalRiskAssessor(config).assess([env], as_of=NOW)[0]


def sensitivity(config):
    result = []
    specifications = [('rainfall', 15, 'rainfall'), ('wbgt', 40, 'heat'),
                      ('pm25', 450, 'air_quality'), ('psi', 500, 'air_quality')]
    for metric, end, component in specifications:
        start = 20 if metric == 'wbgt' else 0
        curve = getattr(config.risk, metric)
        grid = {start + (end-start)*i/120 for i in range(121)}
        for x, _ in curve.points:
            grid.update([max(start, x-.001), x, x+.001])
        # Include the actual input crossing of the component-caution threshold.
        for (x0, y0), (x1, y1) in zip(curve.points, curve.points[1:]):
            if y0 < config.risk.high_score <= y1:
                crossing = x0+(config.risk.high_score-y0)*(x1-x0)/(y1-y0)
                grid.update([crossing-.001, crossing, crossing+.001])
        branches = ['selected'] if metric != 'psi' else ['fallback', 'pm25_preferred']
        for branch in branches:
            previous = -1
            for value in sorted(grid):
                inputs = {metric: value}
                if metric == 'psi' and branch == 'fallback':
                    inputs['pm25'] = None
                risk = assess(config, fixture(values=inputs))
                score = risk.risk_components[component].score
                assert score >= previous and risk.risk_score is not None
                previous = score
                result.append(dict(metric=metric, branch=branch, input_value=value,
                                   component_score=score, total_risk=risk.risk_score,
                                   eligibility=risk.eligibility,
                                   selected_metric=risk.risk_components[component].metric,
                                   rainfall_risk=risk.risk_components['rainfall'].score,
                                   heat_risk=risk.risk_components['heat'].score,
                                   air_risk=risk.risk_components['air_quality'].score,
                                   wind_risk=risk.risk_components['wind'].score))
    return result


def boundary_tests(config):
    """Explicit policy expectations; not inferred from the outputs under test."""
    cases = []
    def add(name, expected, values=None, overrides=None, cfg=None, expected_score='any', expected_level='any'):
        risk = assess(cfg or config, fixture(values=values, overrides=overrides))
        correct_score = expected_score == 'any' or risk.risk_score == expected_score
        cases.append(dict(test=name, policy='default' if cfg is None else 'synthetic_enabled_rule',
                          expected_status=expected, actual_status=risk.eligibility,
                          expected_risk=expected_score, actual_risk=risk.risk_score,
                          expected_level=expected_level, actual_level=risk.risk_level,
                          completeness=risk.risk_data_quality.completeness,
                          heat_input=risk.risk_components['heat'].metric,
                          air_input=risk.risk_components['air_quality'].metric,
                          passed=risk.eligibility == expected and correct_score and
                          (expected_level == 'any' or risk.risk_level == expected_level)))
    add('observed_zero_is_complete', 'eligible', expected_score=0)
    add('saturated_all_inputs_no_default_block', 'caution',
        dict(rainfall=15, wbgt=40, pm25=450), expected_score=95)
    for metric in ('rainfall', 'wind_speed'):
        add('missing_'+metric, 'unknown', {metric: None}, expected_score=None)
    add('all_unavailable', 'unknown', dict.fromkeys(METRICS), expected_score=None)
    add('wbgt_missing_category_fallback', 'caution', {'wbgt': None}, expected_score=7)
    for category, expected_score in [('Moderate', 21), ('High', 31.5)]:
        add('category_fallback_'+category, 'caution',
            dict(wbgt=None, heat_stress_level=category), expected_score=expected_score)
    add('pm25_missing_psi_fallback', 'caution', {'pm25': None}, expected_score=0)
    add('missing_both_heat_inputs', 'unknown', dict(wbgt=None, heat_stress_level=None), expected_score=None)
    add('missing_both_air_inputs', 'unknown', dict(pm25=None, psi=None), expected_score=None)
    add('partial_high_component_is_unknown_without_block_rule', 'unknown',
        dict(rainfall=None, wbgt=35), expected_score=None)
    add('psi_high_ignored_when_pm25_usable', 'eligible', {'psi': 500}, expected_score=0)
    add('numeric_wbgt_overrides_high_category', 'eligible', {'heat_stress_level': 'High'}, expected_score=0)
    for metric in ('rainfall', 'wbgt', 'pm25', 'wind_speed'):
        limit = config.sources[METRIC_SPECS[metric][2]].stale_after_seconds
        for delta in (-1, 0, 1):
            t = NOW-timedelta(seconds=limit+delta)
            expected = 'eligible' if delta <= 0 else 'caution' if metric in {'wbgt', 'pm25'} else 'unknown'
            add(f'{metric}_freshness_limit_{delta:+d}s', expected,
                overrides={metric: dict(observed_at=t, fetched_at=t)})
    for field in ('observed_at', 'fetched_at', 'source_updated_at'):
        add('future_'+field, 'unknown', overrides={'rainfall': {field: NOW+timedelta(seconds=1)}}, expected_score=None)
    add('missing_fetch_timestamp', 'unknown', overrides={'rainfall': {'fetched_at': None}}, expected_score=None)
    add('unit_contract_mismatch', 'unknown', overrides={'rainfall': {'unit': 'cm'}}, expected_score=None)
    for distance, expected in [(1, 'eligible'), (3, 'eligible'), (3.001, 'caution'),
                               (5, 'caution'), (5.001, 'caution'), (15, 'caution'), (15.001, 'unknown')]:
        add(f'station_distance_{distance}', expected,
            overrides={'rainfall': {'station_distance_km': distance}})
    # PM2.5 score crosses component-caution 70 at concentration 190.
    for value, expected in [(189.99, 'eligible'), (190, 'caution'), (190.01, 'caution')]:
        add(f'component_caution_pm25_{value}', expected, {'pm25': value})
    # Rain=60 ->21, WBGT=50 ->17.5. Air=6 ->1.5: total=40.
    # Near-boundary total changes below .005 round to 40, so use +/- .1 concentration.
    for value, expected in [(13.1, 'eligible'), (13.2, 'caution'), (13.3, 'caution')]:
        add(f'total_caution_pm25_{value}', expected, dict(rainfall=5, wbgt=31, pm25=value))
    add('rounding_promotes_just_below_total_40', 'caution',
        dict(rainfall=5, wbgt=31, pm25=13.19), expected_score=40)
    for rainfall, level in [(9.99, 'elevated'), (10, 'high'), (10.01, 'high')]:
        add(f'total_high_rainfall_{rainfall}', 'caution',
            dict(rainfall=rainfall, wbgt=35), expected_level=level)
    for metric, threshold in [('rainfall', 5), ('wbgt', 33), ('pm25', 150), ('psi', 100), ('wind_speed', 20)]:
        cfg = config.model_copy(deep=True)
        cfg.risk.blocking_rules = [BlockingRule(enabled=True, metric=metric, threshold=threshold,
            reason='Analysis-only boundary test, not deployed policy', policy_source='analysis://controlled-fixture')]
        for delta in (-.001, 0, .001):
            base_status = 'caution' if metric == 'wbgt' else 'eligible'
            add(f'synthetic_block_{metric}_{delta:+g}', 'blocked' if delta >= 0 else base_status,
                {metric: threshold+delta}, cfg=cfg)
        add(f'synthetic_stale_cannot_block_{metric}',
            'unknown' if metric in {'rainfall', 'wind_speed'} else 'caution' if metric in {'wbgt', 'pm25'} else 'eligible',
            {metric: threshold}, overrides={metric: {'observed_at': NOW-timedelta(hours=3)}}, cfg=cfg)
        add(f'synthetic_partial_can_block_{metric}', 'blocked',
            {metric: threshold, 'wind_speed' if metric != 'wind_speed' else 'rainfall': None}, cfg=cfg)
    cfg = config.model_copy(deep=True)
    cfg.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=33,
        reason='Analysis-only', policy_source='analysis://fixture')]
    add('approximate_evidence_not_authorized_to_block', 'caution', {'wbgt': 35},
        {'wbgt': {'station_distance_km': 6}}, cfg)
    cfg.risk.blocking_rules[0].allow_approximate_estimates = True
    add('approximate_evidence_explicitly_authorized', 'blocked', {'wbgt': 35},
        {'wbgt': {'station_distance_km': 6}}, cfg)
    return cases


class ArchivedReader:
    """Read-only port: mirrors repository version/availability selection, no locks/writes."""
    def __init__(self, routes):
        self.routes = routes
        self.locations = [typed(Location, row) for row in rows(ROOT/'data/runtime/locations.csv')]
        self.versions = []
        self.current = []
        for group in ('weather', 'heat_stress', 'air_quality'):
            for suffix, target in [('observation_versions', self.versions), ('observations', self.current)]:
                for row in rows(ROOT/f'data/runtime/{group}_{suffix}.csv'):
                    # Only version history through the final evaluation time is needed.
                    if csv_datetime(row['observed_at']) <= NOW:
                        target.append(typed(EnvironmentObservation, row))

    def load_routes(self):
        return self.routes

    def environment_snapshot(self, source_kind, as_of):
        eligible = {}
        def key(o):
            return o.source, o.location_id, o.metric, o.observed_at, o.aggregation_window, o.source_kind
        for o in self.versions:
            if (o.source_kind != source_kind or o.observed_at > as_of or
                (o.first_fetched_at or o.fetched_at) > as_of or
                (o.source_updated_at is not None and o.source_updated_at > as_of)):
                continue
            k = key(o)
            if k not in eligible or o.revision > eligible[k].revision:
                eligible[k] = o
        for o in self.current:
            k = key(o)
            if k in eligible and o.revision == eligible[k].revision and o.fetched_at <= as_of:
                eligible[k] = o
        # Failure logs affect delivery labels only, not scoring. No invented log history.
        return [l for l in self.locations if l.source_kind == source_kind], list(eligible.values()), []


def rank(config, routes, envs, as_of, method='full', environment_weight=None):
    preferences = Preferences(target_distance_km=5, target_difficulty=3)
    risks = EnvironmentalRiskAssessor(config).assess(envs, as_of=as_of)
    conditions = [Conditions(route_id=r.route_id, rainfall_mm=None, station_ids=[], source='unavailable', quality='missing') for r in routes]
    predictions = [Prediction(route_id=r.route_id, horizon_min=30, generated_at=as_of,
        source='evaluation_forecast_disabled', is_mock=False, status='unavailable') for r in routes]
    candidates = BaselineRecommender().rank(routes, conditions, predictions, preferences)
    difficulties = {r.route_id: GenericDifficultyEstimator().predict(r, e).predicted_difficulty for r, e in zip(routes, envs)}
    cfg = config.ranking.model_copy(deep=True)
    if method == 'no_environment' or environment_weight is not None:
        w = 0 if method == 'no_environment' else environment_weight
        remaining = 1-config.ranking.weights['environment']
        weights = {k: (w if k == 'environment' else value*(1-w)/remaining)
                   for k, value in config.ranking.weights.items()}
        cfg = RankingConfig(**(cfg.model_dump() | {'weights': weights}))
    ranked = RiskAwareRanking(cfg).rank(candidates, risks, routes, preferences, difficulties)
    ranked = [r for r in ranked if r.eligibility != 'blocked']
    if method == 'distance':
        # Preserve known-before-unknown group policy in every baseline.
        ranked.sort(key=lambda r: (r.risk_score is None, r.distance_difference_km, r.route_id))
    return ranked, risks, difficulties


def ranking_experiments(config, routes):
    reader = ArchivedReader(routes)
    snapshots = []
    for day in (9, 10, 15):
        as_of = NOW.replace(day=day)
        envs = RouteEnvironmentService(reader, config, 'live').get_all(as_of)
        snapshots.append((f'archived_2026-10-{day:02d}_1200_SGT', as_of, envs))
    # Spatially heterogeneous fixture is deliberately assigned, not real weather.
    controlled = [fixture(r.route_id, dict(rainfall=[0, 1, 10][i % 3],
        wbgt=[26, 31, 35][i % 3], pm25=[0, 55, 350][i % 3])) for i, r in enumerate(routes)]
    snapshots.append(('controlled_heterogeneous', NOW, controlled))
    ranking_rows, summary, weights_rows, environment_rows = [], [], [], []
    for snapshot, as_of, envs in snapshots:
        for e in envs:
            for m in e.metrics:
                environment_rows.append(dict(snapshot=snapshot, **m.model_dump(mode='json', exclude={'sample_provenance'})))
        full_ids = []
        distance_positions = {}
        distance_top = set()
        for method in ('distance', 'no_environment', 'full'):
            ranked, risks, difficulties = rank(config, routes, envs, as_of, method)
            risk_map = {r.route_id: r for r in risks}
            env_map = {e.route_id: {m.metric: m.value for m in e.metrics} for e in envs}
            if method == 'full':
                full_ids = [r.route_id for r in ranked[:3]]
            if method == 'distance':
                distance_positions = {r.route_id: i for i, r in enumerate(ranked, 1)}
                distance_top = {r.route_id for r in ranked[:3]}
            for pos, rec in enumerate(ranked, 1):
                risk = risk_map[rec.route_id]
                selected = {name: (env_map[rec.route_id].get(c.metric) if c.score is not None else None)
                            for name, c in risk.risk_components.items()}
                ranking_rows.append(dict(snapshot=snapshot, method=method, position=pos,
                    route_id=rec.route_id, top3=pos <= 3, eligibility=rec.eligibility,
                    risk_score=rec.risk_score, weighted_score=None if method == 'distance' else rec.recommendation_score,
                    distance_difference_km=rec.distance_difference_km,
                    predicted_difficulty=difficulties[rec.route_id],
                    selected_air=risk.risk_components['air_quality'].metric,
                    usable_selected_air_value=selected['air_quality'],
                    usable_selected_heat_value=selected['heat'],
                    confidence=risk.risk_data_quality.confidence,
                    **{m: env_map[rec.route_id].get(m) for m in ('rainfall', 'wbgt', 'pm25', 'psi')}))
            top = [r for r in ranking_rows if r['snapshot'] == snapshot and r['method'] == method and r['top3']]
            def avg(key):
                vals = [r[key] for r in top if r[key] is not None]
                return sum(vals)/len(vals) if vals else None
            summary.append(dict(snapshot=snapshot, method=method, candidates=len(ranked),
                complete_candidates=sum(r.risk_score is not None for r in ranked),
                blocked_candidates=sum(r.eligibility == 'blocked' for r in risks),
                top3_shared_with_distance=len({r['route_id'] for r in top} & distance_top),
                absolute_rank_shift_from_distance=sum(abs(i-distance_positions[r.route_id]) for i, r in enumerate(ranked, 1)),
                top3=';'.join(r['route_id'] for r in top),
                top3_known_risk_count=sum(r['risk_score'] is not None for r in top),
                mean_top3_risk=avg('risk_score'), mean_top3_recorded_rainfall=avg('rainfall'),
                mean_top3_recorded_wbgt=avg('wbgt'), mean_top3_recorded_pm25=avg('pm25'), mean_top3_recorded_psi=avg('psi'),
                mean_top3_usable_selected_air=avg('usable_selected_air_value'),
                mean_top3_usable_selected_heat=avg('usable_selected_heat_value')))
        for weight in (.30, .45, .60):
            ranked, _, _ = rank(config, routes, envs, as_of, environment_weight=weight)
            ids = [r.route_id for r in ranked[:3]]
            weights_rows.append(dict(snapshot=snapshot, environment_weight=weight,
                top3=';'.join(ids), shared_with_default=len(set(ids) & set(full_ids)),
                jaccard_with_default=len(set(ids) & set(full_ids))/len(set(ids) | set(full_ids)),
                same_order=ids == full_ids))
    return ranking_rows, summary, weights_rows, environment_rows


def save(fig, output, name):
    fig.savefig(output/f'{name}.png', dpi=300)
    fig.savefig(output/f'{name}.pdf', metadata={'CreationDate': None, 'ModDate': None})
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    off_axis_tick_labels = set()
    for ax in fig.axes:
        for axis, limits in [(ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())]:
            low, high = sorted(limits)
            for tick in axis.get_major_ticks():
                if not low <= tick.get_loc() <= high:
                    off_axis_tick_labels.update([tick.label1, tick.label2])
    # Validate visible text against canvas bounds, including long route labels.
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text() and text not in off_axis_tick_labels:
            box = text.get_window_extent(renderer)
            assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.width+1 and box.y1 <= fig.bbox.height+1, text.get_text()
    plt.close(fig)


def plots(output, sensitivity_rows, rankings):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
        'axes.titlesize': 9, 'axes.labelsize': 8, 'xtick.labelsize': 7,
        'ytick.labelsize': 7, 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.7), layout='constrained')
    labels = ['Rainfall (mm; 5-min total)', 'WBGT (°C; 15-min average)',
              'PM2.5 (µg/m³; 1-hour measure)', 'PSI (24-hour index)']
    for i, (ax, metric, label) in enumerate(zip(axes.flat, ('rainfall', 'wbgt', 'pm25', 'psi'), labels)):
        branch = 'fallback' if metric == 'psi' else 'selected'
        data = [r for r in sensitivity_rows if r['metric'] == metric and r['branch'] == branch]
        ax.plot([r['input_value'] for r in data], [r['component_score'] for r in data], color=COLORS[i], label='Selected component')
        ax.plot([r['input_value'] for r in data], [r['total_risk'] for r in data], color='black', linestyle='--', label='Total risk')
        if metric == 'psi':
            ax.plot([0, 500], [0, 0], color='gray', linestyle=':', label='Total with usable PM2.5 = 0')
        ax.set(title=f'({chr(97+i)}) '+ ('PSI fallback; PM2.5 unavailable' if metric == 'psi' else 'PM2.5' if metric == 'pm25' else metric.upper() if metric != 'rainfall' else 'Rainfall'),
               xlabel=label, ylabel='Engineering risk score', ylim=(-3, 104))
        ax.grid(alpha=.18)
        if metric == 'wbgt':
            ax.set_xticks([20, 25, 30, 35, 40])
    handles, labels = axes.flat[-1].get_legend_handles_labels()
    labels[-1] = 'PSI ignored with usable PM2.5'
    fig.legend(handles, labels, loc='outside lower center', ncols=3, fontsize=7)
    save(fig, output, 'figure_1_risk_sensitivity')
    snapshots = list(dict.fromkeys(r['snapshot'] for r in rankings))
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 6.5), layout='constrained')
    for ax, snapshot in zip(axes.flat, snapshots):
        data = [r for r in rankings if r['snapshot'] == snapshot]
        order = [r['route_id'] for r in data if r['method'] == 'full']
        for method, color, marker in zip(('distance', 'no_environment', 'full'), COLORS, ('o', 's', '^')):
            byid = {r['route_id']: r['position'] for r in data if r['method'] == method}
            ax.scatter([byid[r] for r in order], range(len(order)), s=22,
                       color=color, marker=marker, label={'distance':'Distance', 'no_environment':'No environment term', 'full':'Full ranking'}[method], alpha=.8)
        abbreviations = {'rail_corridor_bukit_timah': 'Rail Corridor',
                         'singapore_botanic_gardens': 'Botanic Gardens',
                         'woodlands_waterfront': 'Woodlands',
                         'macritchie_reservoir': 'MacRitchie',
                         'bishan_ang_mo_kio': 'Bishan–AMK',
                         'jurong_lake_gardens': 'Jurong Lake',
                         'punggol_waterway': 'Punggol',
                         'bedok_reservoir': 'Bedok'}
        ax.set_yticks(range(len(order)), [abbreviations.get(r, r.replace('_', ' ').title()) for r in order], fontsize=7)
        ax.invert_yaxis()
        title = snapshot.replace('archived_2026-10-', 'Oct ').replace('_1200_SGT', ', 12:00 SGT').replace('controlled_heterogeneous', 'Controlled heterogeneous')
        if '10-15' in snapshot:
            title += ' (all unknown)'
        ax.set(xlim=(.4, 12.6), xlabel='Rank (1 = first)', title=title)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
        ax.axvspan(.5, 3.5, color='gray', alpha=.08)
        ax.grid(axis='x', alpha=.15)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncols=3, fontsize=7)
    save(fig, output, 'figure_2_ranking_comparison')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT/'data' in output.parents or ROOT/'outdoorwise' in output.parents:
        raise ValueError('Output must be isolated from application/data roots')
    output.mkdir(parents=True, exist_ok=True)
    # Defense in depth: socket connect is forbidden during the entire evaluation.
    def no_network(*args, **kwargs):
        raise RuntimeError('External network access is forbidden in this evaluation')
    socket.socket.connect = no_network
    source_paths = list((ROOT/'outdoorwise').rglob('*.py')) + list((ROOT/'config').glob('*'))
    source_paths += [p for p in (ROOT/'data').rglob('*') if p.is_file() and p.suffix in {'.csv', '.json', '.geojson', '.toml'}]
    before = hashes(source_paths)
    config = load_environment_config(ROOT/'config/environment.toml')
    # Unbound pure loader: no repository constructor, journal recovery or storage writes.
    routes = FileRepository.load_routes(SimpleNamespace(root=ROOT/'data'))
    assert len(routes) == 12
    sensitivity_rows = sensitivity(config)
    cases = boundary_tests(config)
    ranking_rows, summary, weights, environments = ranking_experiments(config, routes)
    for name, data in [('sensitivity.csv', sensitivity_rows), ('eligibility_boundaries.csv', cases),
                       ('ranking_positions.csv', ranking_rows), ('ranking_summary.csv', summary),
                       ('weight_sensitivity.csv', weights), ('matched_environment.csv', environments)]:
        write_csv(output/name, data)
    plots(output, sensitivity_rows, ranking_rows)
    after = hashes(source_paths)
    assert before == after, 'Protected inputs changed during evaluation'
    verification = dict(protected_sha256=before, config=config.model_dump(mode='json'),
        boundary_cases=len(cases), boundary_passes=sum(r['passed'] for r in cases),
        monotonic_checks='passed within explicitly selected branches', network='socket.connect forbidden',
        matplotlib_version=matplotlib.__version__, python_version=sys.version.split()[0])
    (output/'verification.json').write_text(json.dumps(verification, indent=2)+'\n')
    print(json.dumps(dict(boundary_cases=len(cases), passed=sum(r['passed'] for r in cases), ranking_summary=summary), indent=2))
    assert all(r['passed'] for r in cases), 'Boundary expectations failed; inspect CSV rather than change policy'


if __name__ == '__main__':
    main()
