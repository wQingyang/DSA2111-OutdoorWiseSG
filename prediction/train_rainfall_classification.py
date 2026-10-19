"""Predict rain occurrence in future 15-minute station intervals."""

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import average_precision_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "datasets"
    / "snapshot_20261015"
    / "weather_observations.csv"
)

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "rainfall_classification"
)

SGT = ZoneInfo("Asia/Singapore")

INTERVAL_ENDS = list(range(15, 181, 15))
FIVE_MINUTES = timedelta(minutes=5)
STEP = timedelta(minutes=15)

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

METHODS = [
    "always_dry",
    "training_frequency",
    "persistence",
    "logistic_or_prior",
]

CLASSIFICATION_THRESHOLD = 0.5
MIN_CLASS_SAMPLES = 5


def parse_timestamp(value):
    """Interpret stored timestamps as Singapore local time."""
    result = datetime.fromisoformat(value)

    if result.tzinfo is None:
        return result.replace(tzinfo=SGT)

    return result.astimezone(SGT)


def load_stations():
    """Load live five-minute rainfall accumulations by station."""
    stations = defaultdict(dict)

    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["source"] != "nea_rainfall"
                or row["metric"] != "rainfall"
                or row["source_kind"] != "live"
                or not row["value"]
            ):
                continue

            if (
                row["unit"] != "mm"
                or row["aggregation_window"] != "PT5M"
            ):
                raise ValueError(
                    "Unexpected rainfall unit or aggregation window."
                )

            value = float(row["value"])

            fetch_time = (
                row.get("first_fetched_at")
                or row.get("fetched_at")
            )

            if (
                not np.isfinite(value)
                or value < 0
                or not fetch_time
            ):
                continue

            observed = parse_timestamp(row["observed_at"])

            availability_times = [
                observed,
                parse_timestamp(fetch_time),
            ]

            if row.get("source_updated_at"):
                availability_times.append(
                    parse_timestamp(row["source_updated_at"])
                )

            station = row["location_id"]

            if observed in stations[station]:
                raise ValueError(
                    f"Repeated timestamp: {station}, {observed}"
                )

            stations[station][observed] = {
                "value": value,
                "available_at": max(availability_times),
            }

    return stations


def build_samples(records):
    """Assume each five-minute accumulation ends at observed_at."""
    samples = {
        end: [] for end in INTERVAL_ENDS
    }

    origin = min(records).replace(
        second=0,
        microsecond=0,
    )
    origin = origin.replace(
        minute=(origin.minute // 15) * 15
    )

    final_origin = max(records) - STEP

    availability_order = sorted(
        records,
        key=lambda time: records[time]["available_at"],
    )

    position = 0
    latest = None

    while origin <= final_origin:
        # Reveal only observations available at forecast time.
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
            or not timedelta(0) <= origin - latest <= STEP
        ):
            origin += STEP
            continue

        # Six consecutive blocks represent 30 minutes of rainfall.
        history_times = [
            latest - index * FIVE_MINUTES
            for index in range(6)
        ]

        complete_history = all(
            time in records
            and records[time]["available_at"] <= origin
            for time in history_times
        )

        if not complete_history:
            origin += STEP
            continue

        rain_values = [
            records[time]["value"]
            for time in history_times
        ]

        angle = (
            2 * np.pi
            * (origin.hour + origin.minute / 60)
            / 24
        )

        features = rain_values + [
            sum(rain_values[:3]),
            (origin - latest).total_seconds() / 60,
            float(np.sin(angle)),
            float(np.cos(angle)),
        ]

        # Persistence uses rain occurrence in the latest observed 15 minutes.
        current_rain = float(sum(rain_values[:3]) > 0)

        for end in INTERVAL_ENDS:
            interval_end = (
                origin + timedelta(minutes=end)
            )

            # Example: a 0-15 minute target requires blocks ending
            # at origin+5, origin+10 and origin+15 minutes.
            target_times = [
                interval_end - index * FIVE_MINUTES
                for index in range(3)
            ]

            # Missing rainfall blocks must never be treated as dry.
            if any(time not in records for time in target_times):
                continue

            total_rain = sum(
                records[time]["value"]
                for time in target_times
            )

            samples[end].append({
                "origin": origin,
                "end": interval_end,
                "label_available_at": max(
                    records[time]["available_at"]
                    for time in target_times
                ),
                "x": features,
                "y": int(total_rain > 0),
                "persistence": current_rain,
            })

        origin += STEP

    return samples


def training_before(samples, boundary):
    """Exclude labels unavailable before evaluation starts."""
    return [
        sample for sample in samples
        if sample["origin"] < boundary
        and sample["end"] < boundary
        and sample["label_available_at"] < boundary
    ]


def predict_all(train, evaluation):
    """Return three baselines and logistic or frequency fallback."""
    y_train = np.asarray([
        sample["y"] for sample in train
    ])

    prior = float(y_train.mean())

    predictions = {
        "always_dry": np.zeros(len(evaluation)),
        "training_frequency": np.full(
            len(evaluation),
            prior,
        ),
        "persistence": np.asarray([
            sample["persistence"]
            for sample in evaluation
        ]),
    }

    class_counts = np.bincount(
        y_train,
        minlength=2,
    )

    if min(class_counts) < MIN_CLASS_SAMPLES:
        predictions["logistic_or_prior"] = (
            predictions["training_frequency"].copy()
        )

        return (
            predictions,
            "prior_fallback_insufficient_classes",
        )

    # Fit scaling only on the training partition.
    # Avoid class weighting when evaluating raw probabilities.
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0,
            max_iter=1000,
        ),
    )

    model.fit(
        np.asarray([sample["x"] for sample in train]),
        y_train,
    )

    predictions["logistic_or_prior"] = model.predict_proba(
        np.asarray([
            sample["x"] for sample in evaluation
        ])
    )[:, 1]

    return predictions, "logistic_regression"


def calculate_metrics(actual, probability):
    """Evaluate probability quality and rain-event detection."""
    y = np.asarray(actual, dtype=int)
    p = np.asarray(probability, dtype=float)

    predicted = p >= CLASSIFICATION_THRESHOLD

    tp = int(np.sum((y == 1) & predicted))
    fp = int(np.sum((y == 0) & predicted))
    fn = int(np.sum((y == 1) & ~predicted))
    tn = int(np.sum((y == 0) & ~predicted))

    return {
        "samples": len(y),
        "rainy_samples": int(y.sum()),
        "rain_fraction": float(y.mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": (
            2 * tp / (2 * tp + fp + fn)
            if 2 * tp + fp + fn
            else None
        ),
        "average_precision": (
            float(average_precision_score(y, p))
            if len(np.unique(y)) == 2
            else None
        ),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def write_csv(path, rows):
    """Write result tables without changing original data."""
    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
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

    stations = load_stations()

    if not stations:
        raise ValueError("No usable rainfall observations.")

    # Pool stations, but preserve station identifiers in outputs.
    # Split by calendar time, not randomly by station rows.
    all_samples = {
        end: [] for end in INTERVAL_ENDS
    }

    for station, records in sorted(stations.items()):
        station_samples = build_samples(records)

        for end, samples in station_samples.items():
            for sample in samples:
                sample["station"] = station

            all_samples[end].extend(samples)

    summary_rows = []
    station_rows = []
    prediction_rows = []
    skipped = []
    fold_details = []

    for end, samples in all_samples.items():
        train = training_before(samples, cutoff)

        test = [
            sample for sample in samples
            if sample["origin"] >= cutoff
        ]

        if len(train) < 40 or len(test) < 5:
            skipped.append({
                "interval_end_min": end,
                "reason": "Too few training or test samples",
            })
            continue

        validation_actual = []
        validation_probabilities = {
            method: [] for method in METHODS
        }

        used_folds = 0

        for fold_index, (left, right) in enumerate(windows, 1):
            fold_train = training_before(train, left)

            validation = [
                sample for sample in train
                if left <= sample["origin"] < right
            ]

            if len(fold_train) < 20 or len(validation) < 5:
                continue

            probabilities, model_status = predict_all(
                fold_train,
                validation,
            )

            validation_actual.extend(
                sample["y"] for sample in validation
            )

            for method in METHODS:
                validation_probabilities[method].extend(
                    probabilities[method].tolist()
                )

            fold_details.append({
                "interval_end_min": end,
                "fold": fold_index,
                "model_status": model_status,
                "train_samples": len(fold_train),
                "train_rainy_samples": sum(
                    sample["y"] for sample in fold_train
                ),
                "validation_samples": len(validation),
                "validation_rainy_samples": sum(
                    sample["y"] for sample in validation
                ),
            })

            used_folds += 1

        if used_folds < 2:
            skipped.append({
                "interval_end_min": end,
                "reason": "Too few usable validation windows",
            })
            continue

        validation_metrics = {
            method: calculate_metrics(
                validation_actual,
                validation_probabilities[method],
            )
            for method in METHODS
        }

        # Select using validation probability error only.
        selected_method = min(
            METHODS,
            key=lambda method: (
                validation_metrics[method]["brier"]
            ),
        )

        probabilities, model_status = predict_all(
            train,
            test,
        )

        forecasts = {
            **probabilities,
            "selected": probabilities[selected_method],
        }

        actual = [
            sample["y"] for sample in test
        ]

        row = {
            "interval_start_min": end - 15,
            "interval_end_min": end,
            "train_samples": len(train),
            "train_rainy_samples": sum(
                sample["y"] for sample in train
            ),
            "test_samples": len(test),
            "test_rainy_samples": sum(actual),
            "validation_rainy_samples": sum(validation_actual),
            "model_status": model_status,
            "selected_method": selected_method,
        }

        for method in METHODS:
            row[f"validation_{method}_brier"] = (
                validation_metrics[method]["brier"]
            )

        for method, forecast in forecasts.items():
            metrics = calculate_metrics(actual, forecast)

            for name, value in metrics.items():
                row[f"test_{method}_{name}"] = value

        summary_rows.append(row)

        station_indices = defaultdict(list)

        for index, sample in enumerate(test):
            station_indices[sample["station"]].append(index)

            prediction_rows.append({
                "station": sample["station"],
                "forecast_origin": sample["origin"].isoformat(),
                "interval_start": (
                    sample["end"] - STEP
                ).isoformat(),
                "interval_end": sample["end"].isoformat(),
                "actual_rain": sample["y"],
                "model_status": model_status,
                "selected_method": selected_method,
                **{
                    f"{method}_probability": float(values[index])
                    for method, values in forecasts.items()
                },
            })

        for station, indices in sorted(station_indices.items()):
            station_row = {
                "station": station,
                "interval_start_min": end - 15,
                "interval_end_min": end,
            }

            for method, forecast in forecasts.items():
                metrics = calculate_metrics(
                    [actual[index] for index in indices],
                    forecast[indices],
                )

                for name, value in metrics.items():
                    station_row[f"test_{method}_{name}"] = value

            station_rows.append(station_row)

        print(
            f"Finished future interval {end - 15}-{end} minutes",
            flush=True,
        )

    if not summary_rows:
        raise ValueError(
            "No future interval passed the coverage checks."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = [
        ("interval_metrics.csv", summary_rows),
        ("station_interval_metrics.csv", station_rows),
        ("test_predictions.csv", prediction_rows),
    ]

    for filename, rows in tables:
        write_csv(OUTPUT_DIR / filename, rows)

    summary = {
        "holdout_start": cutoff.isoformat(),
        "rain_label": "sum of three 5-minute blocks > 0 mm",
        "model_scope":
            "one shared classifier per future interval across stations",
        "timestamp_assumption":
            "five-minute accumulations end at observed_at",
        "classification_threshold": CLASSIFICATION_THRESHOLD,
        "selection_metric": "validation Brier score",
        "stations_found": len(stations),
        "skipped_intervals": skipped,
        "interval_metrics": summary_rows,
        "validation_details": fold_details,
        "limitations": [
            "Very few wet examples, even after pooling stations.",
            "Station-time samples are correlated, not independent rain events.",
            "Predicted probabilities have not been independently calibrated.",
            "Insufficient classes trigger an explicit frequency fallback.",
            "Undefined precision, recall and AP are null.",
            "Every target interval requires three complete five-minute blocks.",
            "Missing rainfall is never replaced with zero.",
            "Previously inspected dates are reused.",
            "Confirm results on newly collected dates.",
            "Station rain probability is not route-wide coverage.",
            "Rain probability is not rainfall amount in millimetres.",
            "Verify the accumulation timestamp assumption before deployment.",
            "This script does not export production models or a live API.",
        ],
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nHoldout rain classification results:")
    print(
        "Interval(min)  Pairs  Rain  "
        "Persistence Brier  Logistic/prior Brier  Selected Brier"
    )

    for row in summary_rows:
        print(
            f"{row['interval_start_min']:3d}-"
            f"{row['interval_end_min']:<3d} "
            f"{row['test_samples']:8d} "
            f"{row['test_rainy_samples']:5d} "
            f"{row['test_persistence_brier']:18.4f} "
            f"{row['test_logistic_or_prior_brier']:21.4f} "
            f"{row['test_selected_brier']:15.4f}"
        )

    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()