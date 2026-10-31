"""Offline export of the original replay's 15/30-minute neighbor classifiers.

Preserves original preprocessing, C=1, complete-target training rules and the
14 October holdout boundary. Never invoked by an HTTP request.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'prediction'))

import numpy as np
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import train_rainfall_classification as rain
import train_rainfall_neighbors as neighbors
from check_rainfall_sample_rules import build_relaxed_samples
from frozen_rainfall import FEATURE_NAMES, MODEL_PATH, probability


def freeze():
    cutoff = rain.parse_timestamp(rain.HOLDOUT_START)
    stations = rain.load_stations()
    training = {15: [], 30: []}
    origins = set()
    for station, records in sorted(stations.items()):
        samples = build_relaxed_samples(records)
        for horizon in training:
            for sample in rain.training_before(samples[horizon], cutoff):
                if sample['target_complete'] and all(
                    records[sample['end'] - rain.timedelta(minutes=5 * i)]['available_at'] < cutoff
                    for i in range(3)):
                    training[horizon].append(dict(sample, station=station))
                    origins.add(sample['origin'])
    links = neighbors.load_neighbors(stations)
    snapshots = neighbors.build_snapshots(stations, origins)
    models = {}
    for horizon, samples in training.items():
        x = np.asarray([s['x'] + neighbors.neighbor_features(links[s['station']], snapshots[s['origin']])
                        for s in samples])
        y = np.asarray([s['y'] for s in samples])
        if min(np.bincount(y, minlength=2)) < 5:
            raise ValueError('Insufficient classes for a frozen classifier; do not fabricate a model')
        pipeline = make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True),
                                 StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
        pipeline.fit(x, y)
        imputer, scaler, logistic = pipeline.steps[0][1], pipeline.steps[1][1], pipeline.steps[2][1]
        record = dict(imputer_statistics=imputer.statistics_.tolist(),
            missing_indicator_features=imputer.indicator_.features_.tolist(),
            scaler_mean=scaler.mean_.tolist(), scaler_scale=scaler.scale_.tolist(),
            coefficients=logistic.coef_[0].tolist(), intercept=float(logistic.intercept_[0]),
            training_samples=len(y), training_rainy_samples=int(y.sum()),
            latest_training_label_available_at=max(s['label_available_at'] for s in samples).isoformat(),
            latest_training_interval_end=max(s['end'] for s in samples).isoformat())
        # Check the portable export against sklearn on ALL training inputs.
        exported = np.asarray([probability(row, record) for row in x])
        expected = pipeline.predict_proba(x)[:, 1]
        np.testing.assert_allclose(exported, expected, rtol=1e-12, atol=1e-12)
        models[str(horizon)] = record
        print(f'{horizon} min: {len(y)} samples, {int(y.sum())} rainy; export matches sklearn')
    files = [rain.DATA_PATH, neighbors.LOCATION_PATH]
    bundle = dict(schema_version=1, feature_names=FEATURE_NAMES, training_cutoff=cutoff.isoformat(),
        sklearn_version=sklearn.__version__, models=models, neighbors=links,
        dataset_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        limitations=['Historical research only; no probability calibration or new accuracy claim.',
            'Targets are rain-occurrence events, not rainfall amounts or risk scores.',
            'Only native 15/30-minute intervals; no extrapolation to delayed runs.',
            'Snapshot revision history and historical station geography are incomplete.'])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(bundle, indent=2, allow_nan=False) + '\n')
    print(f'Saved {MODEL_PATH}')


if __name__ == '__main__':
    freeze()
