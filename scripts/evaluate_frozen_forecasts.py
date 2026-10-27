"""Offline submission evidence: evaluate frozen PM2.5 and existing persistence.

Never imported by the API. No fitting, parameter selection or source-data writes.
Snapshot availability and revision limitations remain; this is historical evidence.
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'prediction'))
import train_pm25_multihorizon as air
import train_wbgt_multihorizon as heat
import train_rainfall_classification as rain


def evaluate():
    artifact = ROOT / 'prediction/results/pm25_multihorizon/backtest_models.json'
    models = json.loads(artifact.read_text())
    regions = air.load_regions()
    pooled = defaultdict(lambda: {'y': [], 'baseline': [], 'frozen': [], 'times': [], 'locations': set()})
    regional = []
    for region, records in regions.items():
        samples = air.build_samples(records)
        for model in [row for row in models if row['region'] == region]:
            horizon = model['horizon_min']
            cutoff = air.parse_timestamp(model['training_cutoff'])
            eligible = [sample for sample in samples[horizon] if sample['origin'] >= cutoff]
            if not eligible:
                continue
            baseline, linear = air.predict(eligible, model['linear_intercept_and_coefficients'])
            frozen = linear if model['selected_using_validation'] == 'linear' else baseline
            actual = [sample['y'] for sample in eligible]
            regional.append(dict(region=region, horizon_min=horizon, n=len(eligible),
                persistence=air.calculate_metrics(actual, baseline), frozen=air.calculate_metrics(actual, frozen)))
            group = pooled[horizon]
            group['y'].extend(actual); group['baseline'].extend(baseline.tolist()); group['frozen'].extend(frozen.tolist())
            group['times'].extend(sample['origin'] for sample in eligible); group['locations'].add(region)
    pm25 = []
    for horizon, group in sorted(pooled.items()):
        pm25.append(dict(horizon_min=horizon, n=len(group['y']), locations=sorted(group['locations']),
            first_origin=min(group['times']).isoformat(), last_origin=max(group['times']).isoformat(),
            persistence=air.calculate_metrics(group['y'], group['baseline']),
            frozen=air.calculate_metrics(group['y'], group['frozen'])))
    # Report existing baseline errors on the same chronological holdout; no trained WBGT/rain model exists.
    heat_groups = defaultdict(lambda: {'y': [], 'baseline': [], 'locations': set(), 'times': []})
    for station, records in heat.load_stations().items():
        for horizon, samples in heat.build_samples(records).items():
            if horizon not in {15, 30, 60}: continue
            eligible = [row for row in samples if row['origin'] >= heat.parse_timestamp(heat.HOLDOUT_START)]
            group = heat_groups[horizon]
            group['y'].extend(row['y'] for row in eligible)
            group['baseline'].extend(row['x'][0] for row in eligible)
            if eligible:
                group['locations'].add(station); group['times'].extend(row['origin'] for row in eligible)
    wbgt = [dict(horizon_min=horizon, n=len(group['y']), locations=sorted(group['locations']),
        first_origin=min(group['times']).isoformat(), last_origin=max(group['times']).isoformat(),
        persistence=heat.calculate_metrics(group['y'], group['baseline']))
        for horizon, group in sorted(heat_groups.items()) if group['y']]
    rain_groups = defaultdict(lambda: {'y': [], 'baseline': [], 'locations': set(), 'times': []})
    for station, records in rain.load_stations().items():
        for horizon, samples in rain.build_samples(records).items():
            if horizon not in {15, 30}: continue
            eligible = [row for row in samples if row['origin'] >= rain.parse_timestamp(rain.HOLDOUT_START)]
            group = rain_groups[horizon]
            group['y'].extend(row['y'] for row in eligible); group['baseline'].extend(row['persistence'] for row in eligible)
            if eligible:
                group['locations'].add(station); group['times'].extend(row['origin'] for row in eligible)
    rainfall = [dict(interval_end_min=horizon, n=len(group['y']), station_count=len(group['locations']),
        first_origin=min(group['times']).isoformat(), last_origin=max(group['times']).isoformat(),
        persistence=rain.calculate_metrics(group['y'], group['baseline']))
        for horizon, group in sorted(rain_groups.items()) if group['y']]
    return dict(evaluation='offline-frozen-v1', model_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        dataset_sha256={name: hashlib.sha256((ROOT / 'data/datasets/snapshot_20261015' / name).read_bytes()).hexdigest()
            for name in ['air_quality_observations.csv', 'heat_stress_observations.csv', 'weather_observations.csv']},
        training_cutoff='2026-10-14T00:00:00+08:00', pm25=pm25, pm25_by_region=regional,
        wbgt_baseline=wbgt, rainfall_baseline=rainfall,
        limitations=['Static snapshot lacks complete revision history and geography history.',
            'Short chronological holdout with dependent samples; not independent real-world validation.',
            'Rainfall uses strict complete-block samples; missing stations/periods are omitted, never dry.',
            'No rainfall calibration report or frozen logistic artifact; no trained WBGT artifact.',
            'Point-target errors do not validate continuous running-window coverage.',
            'These results do not activate any trained live forecast or forecast-based ranking.'])


if __name__ == '__main__':
    output = ROOT / 'docs/forecast_evaluation.json'
    output.write_text(json.dumps(evaluate(), indent=2) + '\n')
    print(output)
