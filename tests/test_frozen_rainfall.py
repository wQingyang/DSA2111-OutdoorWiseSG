"""Frozen historical rainfall: no request-time fitting or future-label access."""
import copy
import json
import sys
from datetime import timedelta

import pytest
from sklearn.linear_model import LogisticRegression

from outdoorwise.config import ROOT

sys.path.insert(0, str(ROOT / 'prediction'))
import frozen_rainfall as frozen
import predict_route_environment as environment
import train_rainfall_classification as rain

ORIGIN = rain.parse_timestamp('2026-10-15T19:15:00+08:00')


def test_export_cutoff_and_training_classes():
    bundle = json.loads(frozen.MODEL_PATH.read_text())
    cutoff = rain.parse_timestamp(bundle['training_cutoff'])
    assert cutoff < ORIGIN
    assert set(bundle['models']) == {'15', '30'}
    for model in bundle['models'].values():
        assert 5 <= model['training_rainy_samples'] < model['training_samples'] - 5
        assert rain.parse_timestamp(model['latest_training_label_available_at']) < cutoff
        assert rain.parse_timestamp(model['latest_training_interval_end']) < cutoff


def test_real_replay_predicts_without_fitting(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('HTTP inference must not fit a classifier')
    monkeypatch.setattr(LogisticRegression, 'fit', forbidden)
    result = environment.predict('marina_bay', ORIGIN, 0, 30)
    metric = result['metrics']['rain_probability']
    assert len(metric['blocks']) == 2
    for row in metric['blocks']:
        assert 0 <= row['value'] <= 1
        assert row['method'] == 'frozen_experimental_logistic_neighbors'
        assert row['model_version'].startswith('sha256:')
        assert row['input_provenance']
        assert all(rain.parse_timestamp(item['available_at']) <= ORIGIN for item in row['input_provenance'])


def test_future_observations_do_not_change_inference():
    stations = rain.load_stations()
    station = next(identifier for identifier, records in stations.items()
                   if any(t <= ORIGIN and ORIGIN - t <= timedelta(minutes=15)
                          and r['available_at'] <= ORIGIN for t, r in records.items()))
    before = frozen.forecast_blocks(stations, station, ORIGIN, environment.block)
    changed = copy.deepcopy(stations)
    for records in changed.values():
        for time, record in records.items():
            if time > ORIGIN or record['available_at'] > ORIGIN:
                record['value'] = 9999
    assert frozen.forecast_blocks(changed, station, ORIGIN, environment.block) == before


def test_missing_model_is_unavailable(tmp_path):
    rows = frozen.forecast_blocks({}, None, ORIGIN, environment.block, tmp_path / 'absent.json')
    assert all(row['value'] is None for row in rows)
    assert all(row['method'] == 'unavailable_no_frozen_rainfall_model' for row in rows[:2])
    assert all(row['method'] == 'unsupported_rainfall_horizon' for row in rows[2:])


def test_future_model_is_rejected(tmp_path):
    bundle = json.loads(frozen.MODEL_PATH.read_text())
    bundle['training_cutoff'] = (ORIGIN + timedelta(minutes=1)).isoformat()
    path = tmp_path / 'future.json'
    path.write_text(json.dumps(bundle))
    rows = frozen.forecast_blocks({}, None, ORIGIN, environment.block, path)
    assert all(row['value'] is None for row in rows)
    assert rows[0]['method'] == 'unavailable_model_trained_after_origin'


def test_absent_input_and_delayed_window_stay_unavailable():
    assert all(row['value'] is None for row in frozen.forecast_blocks({}, None, ORIGIN, environment.block))
    result = environment.predict('marina_bay', ORIGIN, 30, 30)
    assert all(row['value'] is None and row['method'] == 'unsupported_rainfall_horizon'
               for row in result['metrics']['rain_probability']['blocks'])


def test_portable_probability_including_missing_indicator():
    model = dict(imputer_statistics=[2, 3], missing_indicator_features=[1],
                 scaler_mean=[1, 2, 0], scaler_scale=[2, 1, 1],
                 coefficients=[1, -1, 0.5], intercept=0)
    # [3, NaN] -> impute [3, 3], indicator 1 -> scaled [1, 1, 1]; logit .5
    import math
    assert frozen.probability([3, float('nan')], model) == pytest.approx(1 / (1 + math.exp(-0.5)))
