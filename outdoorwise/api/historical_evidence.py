"""Conservative presentation of native replay targets, separate from evaluation.

The research replay paints direct targets as intervals. Those intervals do not
establish continuous exposure coverage. Keep the values, but do not score a run
as fully assessed on that basis. Evaluation labels never enter inference.
"""
from copy import deepcopy
from functools import lru_cache
import csv
import json

from outdoorwise.config import ROOT
from outdoorwise.contracts.environment import timestamp
from outdoorwise.storage.repository import csv_datetime
from outdoorwise.services.live_prediction import PERSISTENCE_HORIZONS


@lru_cache(maxsize=1)
def evaluation_records():
    records = {}
    folder = ROOT / 'data/datasets/snapshot_20261015'
    for name in ('weather', 'air_quality', 'heat_stress'):
        with (folder / f'{name}_observations.csv').open(newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                if row['source_kind'] == 'live' and row['value']:
                    normalized = {key: csv_datetime(value).isoformat() if key.endswith('_at') and value else value for key, value in row.items()}
                    records[(row['metric'], row['location_id'], csv_datetime(row['observed_at']))] = normalized
    return records


@lru_cache(maxsize=1)
def offline_evaluation():
    path = ROOT / 'docs/forecast_evaluation.json'
    return json.loads(path.read_text()) if path.exists() else None


def describe_forecast(forecast):
    data = deepcopy(forecast)
    origin = timestamp(data['as_of'])
    sources = data['sources']
    records = evaluation_records()
    for name, metric in data['metrics'].items():
        metric['covers_entire_run'] = False
        metric['coverage_status'] = 'Native targets do not establish continuous run-window coverage.'
        source = sources.get('rainfall' if name == 'rain_probability' else name)
        station = source.get('station_id') if isinstance(source, dict) else source
        for block in metric['blocks']:
            target = timestamp(block['valid_to'])
            # Preserve every native research value/method. Applicability to an
            # exact departure and continuous exposure are separate decisions.
            block['target_timestamp'] = block['valid_to']
            block['horizon_min'] = int((target - timestamp(metric['model_origin'])).total_seconds() / 60)
            block['target_semantics'] = ('Probability of any rainfall in the stated 15-minute interval; not rainfall amount or full-run risk.'
                if name == 'rain_probability' else 'Direct point target; displayed interval is not a validated exposure interval.')
            block['input_source'] = source
            block['ground_truth'] = None
            block['forecast_error'] = None
            # Only exact native measurement targets, after the origin, can be
            # compared. Rain event probability needs complete interval labels,
            # not a single rainfall amount at the endpoint.
            truth = records.get((name, station, target)) if name in {'wbgt', 'pm25'} and target > origin else None
            if truth:
                value = float(truth['value'])
                block['ground_truth'] = dict(value=value, observed_at=truth['observed_at'],
                    fetched_at=truth['fetched_at'], first_fetched_at=truth.get('first_fetched_at'),
                    source_updated_at=truth.get('source_updated_at'), source=truth['source'],
                    location_id=station, revision=truth.get('revision'), unit=truth['unit'],
                    aggregation_window=truth['aggregation_window'], usage='evaluation_only')
                if block['value'] is not None:
                    block['forecast_error'] = block['value'] - value
            block['evaluation_status'] = 'Exact target observation available' if truth else 'Exact target ground truth unavailable'
    components = data['forecast_risk']['components']
    start, end = timestamp(data['run_start']), timestamp(data['run_end'])
    for name, item in components.items():
        if name in {'rainfall', 'wind'}:
            metric = 'rainfall' if name == 'rainfall' else 'wind_speed'
            from datetime import timedelta
            valid_to = origin + timedelta(minutes=PERSISTENCE_HORIZONS[metric])
            covered = max(0, (min(end, valid_to) - max(start, origin)).total_seconds() / 60)
            full = covered >= (end-start).total_seconds() / 60
            item.update(valid_from=origin.isoformat(), valid_to=valid_to.isoformat(),
                        coverage_fraction=covered / ((end-start).total_seconds() / 60) if item.get('score') is not None else 0)
            if full:
                continue
        if name in {'heat', 'air_quality'}:
            item['coverage_fraction'] = 0.0
        item.update(score=None, status='incomplete',
                    reason='Unsupported continuous run-window coverage; native estimates remain available for inspection.')
    # No missing-input renormalization or promotion of point forecasts to exposure.
    if any(item['score'] is None for item in components.values()):
        data['forecast_risk'].update(risk_score=None, status='incomplete')
    return data
