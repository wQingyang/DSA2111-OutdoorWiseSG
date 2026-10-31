"""Read-only inference for the frozen historical neighbor-rain experiment.

The JSON stores the fitted median imputer, missing indicators, scaler and
logistic coefficients. No pickle loading, label access or fitting occurs here.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import math

import numpy as np

import train_rainfall_classification as rain
import train_rainfall_neighbors as neighbors

MODEL_PATH = Path(__file__).resolve().parent / 'results/rainfall_neighbors/frozen_model.json'
FEATURE_NAMES = ['latest_5min_mm', 'input_age_min', 'hour_sin', 'hour_cos',
                 *neighbors.NEIGHBOR_FEATURE_NAMES]


@lru_cache(maxsize=4)
def load_model(path, modified_ns):
    """Cache by artifact modification time; missing artifacts remain explicit."""
    raw = Path(path).read_bytes()
    model = json.loads(raw)
    if model['schema_version'] != 1 or model['feature_names'] != FEATURE_NAMES:
        raise ValueError('Unsupported frozen rainfall feature schema')
    model['version'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
    return model


def probability(features, model):
    """Reproduce fitted SimpleImputer -> StandardScaler -> logistic regression."""
    x = np.asarray(features, dtype=float)
    missing = np.isnan(x)
    x = np.where(missing, model['imputer_statistics'], x)
    x = np.concatenate([x, missing[model['missing_indicator_features']].astype(float)])
    z = (x - np.asarray(model['scaler_mean'])) / np.asarray(model['scaler_scale'])
    logit = float(np.dot(z, model['coefficients']) + model['intercept'])
    return 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))


def forecast_blocks(stations, station, origin, block, model_path=None):
    """Predict only the original 0--15 and 15--30-minute event intervals."""
    path = Path(model_path) if model_path is not None else MODEL_PATH
    from datetime import timedelta
    rows = [block(origin + timedelta(minutes=h - 15), origin + timedelta(minutes=h),
                  None, 'unsupported_rainfall_horizon' if h > 30 else 'missing_rainfall_input')
            for h in range(15, 181, 15)]
    try:
        bundle = load_model(str(path), path.stat().st_mtime_ns)
    except FileNotFoundError:
        for row in rows[:2]:
            row['method'] = 'unavailable_no_frozen_rainfall_model'
        return rows
    if rain.parse_timestamp(bundle['training_cutoff']) > origin:
        for row in rows[:2]:
            row['method'] = 'unavailable_model_trained_after_origin'
        return rows
    if station not in bundle['neighbors']:
        return rows
    snapshot = neighbors.build_snapshots(stations, {origin})[origin]
    if station not in snapshot:
        return rows
    value, age = snapshot[station]
    angle = 2 * math.pi * (origin.hour + origin.minute / 60) / 24
    links = bundle['neighbors'][station]
    features = [value, age, math.sin(angle), math.cos(angle),
                *neighbors.neighbor_features(links, snapshot)]
    provenance = []
    for identifier in [station, *[other for other, _ in links]]:
        if identifier not in snapshot:
            continue
        observed = origin - timedelta(minutes=snapshot[identifier][1])
        record = stations[identifier][observed]
        provenance.append(dict(station_id=identifier, value=record['value'],
            observed_at=observed.isoformat(), available_at=record['available_at'].isoformat()))
    for h, row in zip((15, 30), rows[:2]):
        fitted = bundle['models'][str(h)]
        row.update(value=probability(features, fitted), method='frozen_experimental_logistic_neighbors',
            model_version=bundle['version'], model_name='rainfall-neighbors-logistic-v1',
            training_cutoff=bundle['training_cutoff'], training_samples=fitted['training_samples'],
            input_provenance=provenance, calibration_status='Not calibrated; experimental historical model',
            event_definition='Any observed rainfall > 0 mm in the target 15-minute interval')
    return rows
