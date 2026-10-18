"""Direct WBGT forecasts with chronological multi-horizon backtests."""

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import json

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "datasets"
    / "snapshot_20261015"
    / "heat_stress_observations.csv"
)

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "wbgt_multihorizon"
)

SGT = ZoneInfo("Asia/Singapore")

HORIZONS = list(range(15, 181, 15))
STEP = timedelta(minutes=15)
MAX_INPUT_AGE = timedelta(minutes=30)

# Use identical calendar boundaries for all stations and horizons.
HOLDOUT_START = "2026-10-14T00:00:00+08:00"

VALIDATION_WINDOWS = [
    (
        "2026-10-11T00:00:00+08:00",
        "2026-10-12T00:00:00+08:00",
    ),
    (
        "2026-10-12T00:00:00+08:00",
        "2026-10-13T00:00:00+08:00",
    ),
    (
        "2026-10-13T00:00:00+08:00",
        "2026-10-14T00:00:00+08:00",
    ),
]

FEATURE_NAMES = [
    "latest_wbgt",
    "lag_15min",
    "lag_30min",
    "lag_45min",
    "lag_60min",
    "observation_age_min",
    "hour_sin",
    "hour_cos",
]


def parse_timestamp(value):
    """Interpret stored timestamps as Singapore local time."""
    result = datetime.fromisoformat(value)

    if result.tzinfo is None:
        return result.replace(tzinfo=SGT)

    return result.astimezone(SGT)


def load_stations():
    """Load live WBGT observations grouped by station."""
    stations = defaultdict(dict)

    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["source"] != "nea_wbgt"
                or row["metric"] != "wbgt"
                or row["source_kind"] != "live"
                or not row["value"]
            ):
                continue

            value = float(row["value"])

            fetch_time = (
                row.get("first_fetched_at")
                or row.get("fetched_at")
            )

            if not np.isfinite(value) or not fetch_time:
                continue

            observed_at = parse_timestamp(row["observed_at"])

            availability_times = [
                observed_at,
                parse_timestamp(fetch_time),
            ]

            if row.get("source_updated_at"):
                availability_times.append(
                    parse_timestamp(row["source_updated_at"])
                )

            station = row["location_id"]

            if observed_at in stations[station]:
                raise ValueError(
                    f"Repeated timestamp: {station}, {observed_at}"
                )

            stations[station][observed_at] = {
                "value": value,
                "available_at": max(availability_times),
            }

    return stations


def build_samples(records):
    """Match future labels by timestamp, never by row position."""
    samples = {horizon: [] for horizon in HORIZONS}

    origin = min(records).replace(second=0, microsecond=0)
    origin = origin.replace(
        minute=(origin.minute // 15) * 15
    )

    final_origin = (
        max(records)
        - timedelta(minutes=min(HORIZONS))
    )

    availability_order = sorted(
        records,
        key=lambda time: records[time]["available_at"],
    )

    position = 0
    latest = None

    while origin <= final_origin:
        # Reveal only observations already available at forecast time.
        while position < len(availability_order):
            observed = availability_order[position]

            if records[observed]["available_at"] > origin:
                break

            latest = (
                max(latest, observed)
                if latest is not None
                else observed
            )
            position += 1

        if (
            latest is None
            or not timedelta(0)
            <= origin - latest
            <= MAX_INPUT_AGE
        ):
            origin += STEP
            continue

        # Require five consecutive readings spanning one hour.
        history = [
            latest - index * STEP
            for index in range(5)
        ]

        complete_history = all(
            time in records
            and records[time]["available_at"] <= origin
            for time in history
        )

        if not complete_history:
            origin += STEP
            continue

        hour = origin.hour + origin.minute / 60
        angle = 2 * np.pi * hour / 24

        features = [
            records[time]["value"]
            for time in history
        ]
        features.extend([
            (origin - latest).total_seconds() / 60,
            float(np.sin(angle)),
            float(np.cos(angle)),
        ])

        # Build separate direct targets for every forecast horizon.
        for horizon in HORIZONS:
            target_time = origin + timedelta(minutes=horizon)

            if target_time not in records:
                continue

            samples[horizon].append({
                "origin": origin,
                "target": target_time,
                "latest": latest,
                "x": features,
                "y": records[target_time]["value"],
                "target_available_at":
                    records[target_time]["available_at"],
            })

        origin += STEP

    return samples


def training_before(samples, boundary):
    """Purge training labels unavailable before evaluation starts."""
    return [
        sample for sample in samples
        if sample["origin"] < boundary
        and sample["target"] < boundary
        and sample["target_available_at"] < boundary
    ]


def fit_linear(train):
    """Fit a separate direct linear model using training data only."""
    x_train = np.asarray([
        sample["x"] for sample in train
    ])
    y_train = np.asarray([
        sample["y"] for sample in train
    ])

    design = np.column_stack([
        np.ones(len(train)),
        x_train,
    ])

    coefficients, _, _, _ = np.linalg.lstsq(
        design,
        y_train,
        rcond=None,
    )

    return coefficients


def predict(samples, coefficients):
    """Return persistence and direct linear predictions."""
    x = np.asarray([
        sample["x"] for sample in samples
    ])

    baseline = x[:, 0]

    design = np.column_stack([
        np.ones(len(samples)),
        x,
    ])
    linear = design @ coefficients

    return baseline, linear


def calculate_metrics(actual, predicted):
    """Calculate errors in degrees Celsius."""
    error = np.asarray(predicted) - np.asarray(actual)

    return {
        "mae_degC": float(np.mean(np.abs(error))),
        "rmse_degC": float(np.sqrt(np.mean(error ** 2))),
    }


def write_csv(path, rows):
    """Write a result table without changing source data."""
    if not rows:
        return

    with path.open(newline="", mode="w", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    cutoff = parse_timestamp(HOLDOUT_START)

    windows = [
        (parse_timestamp(start), parse_timestamp(end))
        for start, end in VALIDATION_WINDOWS
    ]

    if any(not start < end <= cutoff for start, end in windows):
        raise ValueError(
            "Validation windows must end no later than holdout start."
        )

    for previous, current in zip(windows, windows[1:]):
        if previous[1] > current[0]:
            raise ValueError(
                "Validation windows must be ordered and non-overlapping."
            )

    stations = load_stations()

    if not stations:
        raise ValueError("No usable live WBGT observations.")

    metric_rows = []
    prediction_rows = []
    saved_models = []
    skipped = []
    fold_details = []

    pooled = {
        horizon: {
            "actual": [],
            "baseline": [],
            "linear": [],
            "selected": [],
        }
        for horizon in HORIZONS
    }

    for station, records in sorted(stations.items()):
        samples_by_horizon = build_samples(records)

        for horizon, samples in samples_by_horizon.items():
            train = training_before(samples, cutoff)

            test = [
                sample for sample in samples
                if sample["origin"] >= cutoff
            ]

            if len(train) < 40 or len(test) < 5:
                skipped.append({
                    "station": station,
                    "horizon_min": horizon,
                    "reason": "Insufficient training or test samples",
                    "train_samples": len(train),
                    "test_samples": len(test),
                })
                continue

            validation_actual = []
            validation_baseline = []
            validation_linear = []
            used_folds = 0

            for fold_index, (left, right) in enumerate(windows, 1):
                fold_train = training_before(train, left)

                validation = [
                    sample for sample in train
                    if left <= sample["origin"] < right
                ]

                if len(fold_train) < 20 or len(validation) < 5:
                    continue

                fold_coefficients = fit_linear(fold_train)

                baseline, linear = predict(
                    validation,
                    fold_coefficients,
                )

                actual = [
                    sample["y"] for sample in validation
                ]

                validation_actual.extend(actual)
                validation_baseline.extend(baseline.tolist())
                validation_linear.extend(linear.tolist())

                used_folds += 1

                fold_details.append({
                    "station": station,
                    "horizon_min": horizon,
                    "fold": fold_index,
                    "window_start": left.isoformat(),
                    "window_end_exclusive": right.isoformat(),
                    "train_samples": len(fold_train),
                    "validation_samples": len(validation),
                    "baseline": calculate_metrics(actual, baseline),
                    "linear": calculate_metrics(actual, linear),
                })

            if used_folds < 2:
                skipped.append({
                    "station": station,
                    "horizon_min": horizon,
                    "reason": "Fewer than two usable validation windows",
                })
                continue

            validation_base_metrics = calculate_metrics(
                validation_actual,
                validation_baseline,
            )
            validation_linear_metrics = calculate_metrics(
                validation_actual,
                validation_linear,
            )

            # Select only using training-period validation MAE.
            # Ties retain the simpler persistence baseline.
            selected_method = (
                "linear"
                if (
                    validation_linear_metrics["mae_degC"]
                    < validation_base_metrics["mae_degC"]
                )
                else "baseline"
            )

            # Fit the station/horizon model before the holdout cutoff.
            coefficients = fit_linear(train)
            baseline, linear = predict(test, coefficients)

            selected_predictions = (
                linear
                if selected_method == "linear"
                else baseline
            )

            actual = [sample["y"] for sample in test]

            metric_row = {
                "station": station,
                "horizon_min": horizon,
                "train_samples": len(train),
                "test_samples": len(test),
                "validation_samples": len(validation_actual),
                "validation_folds": used_folds,
                "selected_using_validation": selected_method,
                "validation_baseline_mae":
                    validation_base_metrics["mae_degC"],
                "validation_linear_mae":
                    validation_linear_metrics["mae_degC"],
            }

            forecasts = [
                ("baseline", baseline),
                ("linear", linear),
                ("selected", selected_predictions),
            ]

            for method, forecast in forecasts:
                for name, value in calculate_metrics(
                    actual, forecast
                ).items():
                    metric_row[f"holdout_{method}_{name}"] = value

            metric_rows.append(metric_row)

            # These are frozen backtest models, not deployment models.
            saved_models.append({
                "station": station,
                "horizon_min": horizon,
                "selected_using_validation": selected_method,
                "training_cutoff": cutoff.isoformat(),
                "linear_intercept_and_coefficients":
                    coefficients.tolist(),
            })

            values_to_pool = [
                ("actual", actual),
                ("baseline", baseline),
                ("linear", linear),
                ("selected", selected_predictions),
            ]

            for name, values in values_to_pool:
                pooled[horizon][name].extend(values)

            for sample, base, lin, selected in zip(
                test,
                baseline,
                linear,
                selected_predictions,
            ):
                prediction_rows.append({
                    "station": station,
                    "horizon_min": horizon,
                    "forecast_origin": sample["origin"].isoformat(),
                    "target_time": sample["target"].isoformat(),
                    "latest_observed_at": sample["latest"].isoformat(),
                    "actual_wbgt": sample["y"],
                    "baseline_wbgt": float(base),
                    "linear_wbgt": float(lin),
                    "selected_wbgt": float(selected),
                    "selected_method": selected_method,
                })

    if not metric_rows:
        raise ValueError(
            "No station/horizon passed the sample coverage checks."
        )

    horizon_rows = []

    for horizon, values in pooled.items():
        if not values["actual"]:
            continue

        row = {
            "horizon_min": horizon,
            "station_time_pairs": len(values["actual"]),
            "stations_evaluated": sum(
                item["horizon_min"] == horizon
                for item in metric_rows
            ),
        }

        for method in ["baseline", "linear", "selected"]:
            metrics = calculate_metrics(
                values["actual"],
                values[method],
            )

            for name, value in metrics.items():
                row[f"{method}_{name}"] = value

        horizon_rows.append(row)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = [
        ("station_horizon_metrics.csv", metric_rows),
        ("horizon_metrics.csv", horizon_rows),
        ("test_predictions.csv", prediction_rows),
    ]

    for filename, rows in tables:
        write_csv(OUTPUT_DIR / filename, rows)

    summary = {
        "holdout_start": cutoff.isoformat(),
        "stations_found": len(stations),
        "horizons_minutes": HORIZONS,
        "feature_names": FEATURE_NAMES,
        "horizon_metrics": horizon_rows,
        "skipped_pairs": skipped,
        "validation_details": fold_details,
        "limitations": [
            "Later snapshot dates were inspected in earlier experiments.",
            "Holdout comparisons are exploratory.",
            "Confirm performance on newly collected dates.",
            "Station-time forecasts overlap and are correlated.",
            "Complete observation revision history is unavailable.",
            "Targets are future 15-minute WBGT means.",
            "Different horizons can have different valid samples.",
            "Methods use matched samples within each horizon.",
            "Saved models are frozen backtest models, not deployment models.",
            "Rainfall, air quality, risk integration and live APIs are not included.",
        ],
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    (OUTPUT_DIR / "backtest_models.json").write_text(
        json.dumps(saved_models, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Holdout WBGT errors (degrees Celsius):")
    print(
        "Min  Stations  Pairs  "
        "Baseline MAE  Linear MAE  Selected MAE"
    )

    for row in horizon_rows:
        print(
            f"{row['horizon_min']:3d} "
            f"{row['stations_evaluated']:8d} "
            f"{row['station_time_pairs']:6d} "
            f"{row['baseline_mae_degC']:13.4f} "
            f"{row['linear_mae_degC']:11.4f} "
            f"{row['selected_mae_degC']:13.4f}"
        )

    print(f"\nSkipped station/horizon pairs: {len(skipped)}")
    print(f"Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()