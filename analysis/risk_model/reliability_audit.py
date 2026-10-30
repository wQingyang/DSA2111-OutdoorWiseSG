"""Offline provenance and polling audit; no repository construction or collectors."""
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import datetime
from pathlib import Path

from analysis.data_freshness.session_audit import (
    classify_runs, evaluate_source, local_time, minutes, read_runs,
)
from outdoorwise.contracts.environment import RouteMetric
from outdoorwise.contracts.ports import collection_error_category
from outdoorwise.modules.risk import EnvironmentalRiskAssessor

ROOT = Path(__file__).resolve().parents[2]


def audit(config, environment_rows, ranking_rows):
    logs = read_runs(ROOT/'data/runtime/ingestion_runs.csv')
    logs = [r for r in logs if r['source_kind'] == 'live']
    by_source = defaultdict(list)
    for r in logs:
        by_source[r['source']].append(r)
    for runs in by_source.values():
        runs.sort(key=lambda r: r['_start'])
    metric_audit, coverage, negative = [], [], []
    assessor = EnvironmentalRiskAssessor(config)
    for snapshot in dict.fromkeys(r['snapshot'] for r in environment_rows):
        selected = [r for r in environment_rows if r['snapshot'] == snapshot]
        full = [r for r in ranking_rows if r['snapshot'] == snapshot and r['method'] == 'full']
        counts = Counter(r['eligibility'] for r in full)
        states = Counter()
        for row in selected:
            m = RouteMetric.model_validate({k: v for k, v in row.items() if k != 'snapshot'})
            component = assessor.measurement(m, m.as_of)
            states[(m.metric, 'usable' if component.score is not None else component.freshness)] += 1
            if not snapshot.startswith('archived_'):
                continue
            runs = by_source[m.source]
            prior = [r for r in runs if r['_end'] <= m.as_of]
            successes = [r for r in prior if r['status'] == 'success']
            next_runs = [r for r in runs if r['_start'] > m.as_of]
            last = prior[-1] if prior else None
            success = successes[-1] if successes else None
            metric_audit.append(dict(snapshot=snapshot, as_of=m.as_of.isoformat(),
                route_id=m.route_id, metric=m.metric, source=m.source, location_id=m.location_id,
                value=m.value, category_value=m.category_value, observed_at=m.observed_at.isoformat() if m.observed_at else None,
                selected_version_fetch_evidence_at=m.fetched_at.isoformat() if m.fetched_at else None,
                source_updated_at=m.source_updated_at.isoformat() if m.source_updated_at else None,
                observation_age_minutes=minutes(m.as_of, m.observed_at) if m.observed_at else None,
                freshness_limit_minutes=config.sources[m.source].stale_after_seconds/60,
                freshness=component.freshness, usable=component.score is not None,
                spatial_quality=component.spatial_quality, estimate_status=component.estimate_status,
                last_attempt_started_at=last['started_at'] if last else None,
                last_attempt_status=last['status'] if last else None,
                last_successful_run_finished_at=success['finished_at'] if success else None,
                last_success_log_line=success['_log_line'] if success else None,
                next_recorded_attempt_started_at=next_runs[0]['started_at'] if next_runs else None,
                minutes_since_success_finish=minutes(m.as_of, success['_end']) if success else None,
                failures_in_previous_2h=sum(r['status'] == 'failed' and minutes(m.as_of, r['_end']) <= 120 for r in prior),
                polling_records_in_previous_15min=sum(minutes(m.as_of, r['_end']) <= 15 for r in prior),
                cause='selected evidence stale' if component.freshness == 'stale' else
                      'usable archived evidence' if component.score is not None else '; '.join(component.warnings),
                process_state_at_as_of='not established by retained process logs'))
        item = dict(snapshot=snapshot, routes=len(full), complete=sum(r['risk_score'] is not None for r in full),
                    eligible=counts['eligible'], caution=counts['caution'], blocked=counts['blocked'], unknown=counts['unknown'],
                    very_low_confidence_routes=sum(r['confidence'] == 'very_low' for r in full),
                    fresh_rainfall_routes=states[('rainfall', 'usable')],
                    fresh_wind_routes=states[('wind_speed', 'usable')],
                    usable_wbgt_routes=states[('wbgt', 'usable')],
                    usable_pm25_routes=states[('pm25', 'usable')], usable_psi_routes=states[('psi', 'usable')])
        coverage.append(item)
        if '10-15' in snapshot:
            negative.append(dict(**item, interpretation='unknown assessment; discovery only',
                risk_score='null', weighted_score='null', fallback='legacy distance order; no location or forecast',
                visible_disclosure='Assessment unavailable; Unknown; fallback message',
                root_cause='stale required observations at selected evaluation time; interruption cause unproven'))
        elif snapshot.startswith('archived_'):
            assert item['complete'] == 12, f'Primary snapshot has insufficient coverage: {snapshot}'

    gap_rows, polling_summary = [], []
    cfg = config.collection
    duration_limit = ((cfg.max_retries+1)*cfg.timeout_seconds + cfg.max_retries*cfg.max_retry_delay_seconds +
                      cfg.request_spacing_seconds + 30)/60
    for source, runs in sorted(by_source.items()):
        interval = config.sources[source].interval_seconds/60
        classified = classify_runs(runs, interval, duration_limit)
        for previous, current in zip(classified, classified[1:]):
            quiet = minutes(current['_start'], previous['_end'])
            if quiet > 2*interval+.5:
                gap_rows.append(dict(source=source, previous_run_id=previous['run_id'],
                    previous_finished_at=previous['finished_at'], previous_status=previous['status'],
                    next_run_id=current['run_id'], next_started_at=current['started_at'], next_status=current['status'],
                    no_recorded_attempt_gap_minutes=quiet, expected_poll_interval_minutes=interval,
                    gap_excess_over_one_interval_minutes=max(0, quiet-interval),
                    classification='extended' if quiet > 4*interval+.5 else 'irregular',
                    evidence='no completed source attempt recorded between endpoints; process/sleep/network cause unknown'))
        gaps = [r for r in gap_rows if r['source'] == source]
        polling_summary.append(dict(source=source, poll_interval_minutes=interval,
            attempts=len(runs), successes=sum(r['status'] == 'success' for r in runs),
            failures=sum(r['status'] == 'failed' for r in runs),
            active_successes=sum(r['_state'] == 'active' for r in classified),
            irregular_or_extended_gaps=len(gaps), extended_gaps=sum(r['classification'] == 'extended' for r in gaps),
            maximum_gap_minutes=max((r['no_recorded_attempt_gap_minutes'] for r in gaps), default=0),
            independently_verified_process_outages=0,
            process_outage_interpretation='not identifiable; zero verified does not imply zero actual outages'))

    direct = defaultdict(lambda: Counter())
    starts = {source: [r['_start'] for r in runs] for source, runs in by_source.items()}
    # Direct evidence covers retained acquisitions/revisions; unchanged payloads are absent.
    for group, metric in [('weather', 'rainfall'), ('heat_stress', 'wbgt'), ('air_quality', 'pm25'), ('air_quality', 'psi')]:
        with (ROOT/f'data/runtime/{group}_observation_versions.csv').open(newline='') as handle:
            for row in csv.DictReader(handle):
                if row['metric'] != metric or row['source_kind'] != 'live' or not row['value']:
                    continue
                source = row['source']; fetched = local_time(row['fetched_at'])
                index = bisect_right(starts[source], fetched)-1
                if index < 0:
                    raise ValueError('No acquisition run for retained revision')
                run = by_source[source][index]
                assert run['status'] == 'success' and fetched <= run['_end']
                age = minutes(fetched, local_time(row['observed_at']))
                kind = 'stale_version' if age > config.sources[source].stale_after_seconds/60 else 'fresh_version'
                direct[(source, run['run_id'])][kind] += 1
    operational = []
    for group, metric, source, cadence in [('weather', 'rainfall', 'nea_rainfall', 5),
            ('heat_stress', 'wbgt', 'nea_wbgt', 15), ('air_quality', 'pm25', 'nea_pm25', 60),
            ('air_quality', 'psi', 'nea_psi', 60)]:
        result = evaluate_source(ROOT/f'data/runtime/{group}_observation_versions.csv', logs,
            metric, source, metric, config.sources[source].interval_seconds/60, duration_limit, cadence,
            5 if metric == 'rainfall' else 15)
        successful = [r for r in result['run_rows'] if r['status'] == 'success']
        active = [r for r in result['run_rows'] if r['qualifying_active_success']]
        for selection, runs in [('all_successful', successful), ('active_successful', active)]:
            operational.append(dict(source=source, selection=selection, successful_runs=len(runs),
                runs_with_direct_retained_fresh_versions=sum(direct[(source, r['run_id'])]['fresh_version'] > 0 for r in runs),
                runs_with_direct_retained_stale_versions=sum(direct[(source, r['run_id'])]['stale_version'] > 0 for r in runs),
                runs_demonstrably_stale_from_acquisition_bound=sum(
                    r['returned_age_lower_bound_minutes'] is not None and
                    r['returned_age_lower_bound_minutes'] > config.sources[source].stale_after_seconds/60 for r in runs),
                active_runs_demonstrably_over_60_minutes=sum(r['demonstrated_over_60_minutes'] for r in runs),
                maximum_active_age_lower_bound_minutes=max((r['returned_age_lower_bound_minutes'] for r in runs
                    if r['returned_age_lower_bound_minutes'] is not None), default=None),
                freshness_limit_minutes=config.sources[source].stale_after_seconds/60,
                observation_cadence_minutes=cadence,
                interpretation='direct retained versions cover some responses; bounds only evaluated on qualifying active runs; categories can overlap'))
    failures = Counter((r['source'], collection_error_category(r['error'])) for r in logs if r['status'] == 'failed')
    failure_rows = [dict(source=s, error_category=c, failed_runs=n,
        interpretation='recorded failed request/parse; not proof of local process shutdown') for (s, c), n in sorted(failures.items())]
    effects = []
    for snapshot in dict.fromkeys(r['snapshot'] for r in ranking_rows):
        full = [r for r in ranking_rows if r['snapshot'] == snapshot and r['method'] == 'full']
        for baseline in ('distance', 'no_environment'):
            other = [r for r in ranking_rows if r['snapshot'] == snapshot and r['method'] == baseline]
            positions = {r['route_id']: r['position'] for r in other}
            a, b = ({r['route_id'] for r in data if r['position'] <= 3} for data in (full, other))
            def mean(data):
                values = [r['risk_score'] for r in data if r['position'] <= 3 and r['risk_score'] is not None]
                return sum(values)/len(values) if values else None
            full_mean, base_mean = mean(full), mean(other)
            effects.append(dict(snapshot=snapshot, comparison='full_vs_'+baseline,
                routes_changed=sum(r['position'] != positions[r['route_id']] for r in full),
                top3_shared=len(a & b), top3_gained=';'.join(sorted(a-b)), top3_lost=';'.join(sorted(b-a)),
                baseline_mean_top3_risk=base_mean, full_mean_top3_risk=full_mean,
                change_mean_top3_internal_risk=full_mean-base_mean if full_mean is not None and base_mean is not None else None))
    return dict(snapshot_metric_audit=metric_audit, snapshot_coverage=coverage, ranking_effects=effects,
        missing_data_negative_control=negative, collector_polling_summary=polling_summary,
        collector_gaps=gap_rows, collector_response_evidence=operational, collector_failure_categories=failure_rows)
