"""Compare local and neighboring-station rainfall features on matched rows."""

from pathlib import Path
from collections import defaultdict
from math import radians, sin, cos, asin, sqrt
from datetime import timedelta
import csv
import json

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

import train_rainfall_classification as rain
from check_rainfall_sample_rules import build_relaxed_samples


PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOCATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "datasets"
    / "snapshot_20261015"
    / "locations.csv"
)

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "rainfall_neighbors"
)

NEIGHBOR_COUNT = 5
MAX_DISTANCE_KM = 10.0
MAX_NEIGHBOR_AGE = timedelta(minutes=15)

METHODS = [
    "always_dry",
    "training_frequency",
    "persistence",
    "logistic_local",
    "logistic_neighbors",
]

NEIGHBOR_FEATURE_NAMES = [
    "usable_neighbor_fraction",
    "neighbor_rain_fraction",
    "neighbor_mean_5min_mm",
    "neighbor_max_5min_mm",
    "nearest_wet_neighbor_km",
    "neighbor_mean_age_min",
]


def distance_km(point_a, point_b):
    """Calculate great-circle distance between latitude/longitude points."""
    lat1, lon1 = map(radians, point_a)
    lat2, lon2 = map(radians, point_b)

    value = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin((lon2 - lon1) / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    return 6371.0088 * 2 * asin(sqrt(value))


def load_neighbors(stations):
    """Select fixed nearby stations from the location snapshot."""
    coordinates = {}

    with LOCATION_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["source"] != "nea_rainfall"
                or row["source_kind"] != "live"
                or row["location_type"] != "station"
            ):
                continue

            point = (
                float(row["lat"]),
                float(row["lon"]),
            )

            if not all(np.isfinite(point)):
                continue

            station = row["location_id"]

            if (
                station in coordinates
                and coordinates[station] != point
            ):
                raise ValueError(
                    f"Conflicting coordinates for {station}"
                )

            coordinates[station] = point

    neighbors = {}

    for station in stations:
        if station not in coordinates:
            raise ValueError(
                f"Missing coordinates for {station}"
            )

        candidates = sorted(
            (
                distance_km(
                    coordinates[station],
                    coordinates[other],
                ),
                other,
            )
            for other in stations
            if other != station
            and other in coordinates
        )

        neighbors[station] = [
            (other, distance)
            for distance, other in candidates
            if distance <= MAX_DISTANCE_KM
        ][:NEIGHBOR_COUNT]

    return neighbors


def build_snapshots(stations, origins):
    """Use only readings available at each historical forecast origin."""
    availability_order = {
        station: sorted(
            records,
            key=lambda time: records[time]["available_at"],
        )
        for station, records in stations.items()
    }

    positions = {
        station: 0 for station in stations
    }

    latest = {
        station: None for station in stations
    }

    snapshots = {}

    for origin in sorted(origins):
        snapshot = {}

        for station, records in stations.items():
            sequence = availability_order[station]

            while positions[station] < len(sequence):
                observed = sequence[positions[station]]

                if records[observed]["available_at"] > origin:
                    break

                latest[station] = (
                    max(latest[station], observed)
                    if latest[station] is not None
                    else observed
                )

                positions[station] += 1

            observed = latest[station]

            if (
                observed is not None
                and timedelta(0)
                <= origin - observed
                <= MAX_NEIGHBOR_AGE
            ):
                assert records[observed]["available_at"] <= origin

                snapshot[station] = (
                    records[observed]["value"],
                    (origin - observed).total_seconds() / 60,
                )

        snapshots[origin] = snapshot

    return snapshots


def neighbor_features(neighbors, snapshot):
    """Summarize available nearby readings and preserve missingness."""
    available = [
        (
            snapshot[station][0],
            snapshot[station][1],
            distance,
        )
        for station, distance in neighbors
        if station in snapshot
    ]

    coverage = (
        len(available) / len(neighbors)
        if neighbors
        else 0.0
    )

    if not available:
        return [
            coverage,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
        ]

    values = [
        value for value, _, _ in available
    ]

    wet_distances = [
        distance
        for value, _, distance in available
        if value > 0
    ]

    return [
        coverage,
        float(np.mean(np.asarray(values) > 0)),
        float(np.mean(values)),
        float(max(values)),
        min(wet_distances) if wet_distances else np.nan,
        float(np.mean([
            age for _, age, _ in available
        ])),
    ]


def predict_methods(train, evaluation):
    """Fit local and neighbor models using training-only preprocessing."""
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

    statuses = {}

    feature_sets = [
        ("logistic_local", "x"),
        ("logistic_neighbors", "neighbor_x"),
    ]

    for method, feature_key in feature_sets:
        if min(np.bincount(y_train, minlength=2)) < 5:
            predictions[method] = np.full(
                len(evaluation),
                prior,
            )

            statuses[method] = (
                "prior_fallback_insufficient_classes"
            )
            continue

        # Fit imputation and scaling inside each training partition.
        # Missing indicators and coverage distinguish missingness from rain=0.
        model = make_pipeline(
            SimpleImputer(
                strategy="median",
                add_indicator=True,
                keep_empty_features=True,
            ),
            StandardScaler(),
            LogisticRegression(
                C=1.0,
                max_iter=1000,
            ),
        )

        model.fit(
            np.asarray([
                sample[feature_key] for sample in train
            ]),
            y_train,
        )

        predictions[method] = model.predict_proba(
            np.asarray([
                sample[feature_key]
                for sample in evaluation
            ])
        )[:, 1]

        statuses[method] = "logistic_regression"

    return predictions, statuses


def main():
    if not LOCATION_PATH.exists():
        raise FileNotFoundError(
            f"Locations file not found: {LOCATION_PATH}"
        )

    stations = rain.load_stations()

    if not stations:
        raise ValueError("No usable rainfall observations.")

    neighbors = load_neighbors(stations)

    samples_by_interval = {
        end: [] for end in rain.INTERVAL_ENDS
    }

    origins = set()

    # Keep complete future targets for all training and evaluation methods.
    for station, records in sorted(stations.items()):
        station_samples = build_relaxed_samples(records)

        for end, samples in station_samples.items():
            for sample in samples:
                if not sample["target_complete"]:
                    continue

                if len(sample["x"]) != 4:
                    raise ValueError(
                        "Expected four local features from "
                        "build_relaxed_samples."
                    )

                sample["station"] = station
                samples_by_interval[end].append(sample)
                origins.add(sample["origin"])

    snapshots = build_snapshots(stations, origins)

    feature_cache = {}

    for samples in samples_by_interval.values():
        for sample in samples:
            key = (
                sample["station"],
                sample["origin"],
            )

            if key not in feature_cache:
                feature_cache[key] = neighbor_features(
                    neighbors[sample["station"]],
                    snapshots[sample["origin"]],
                )

            sample["neighbor_x"] = (
                sample["x"] + feature_cache[key]
            )

    cutoff = rain.parse_timestamp(rain.HOLDOUT_START)

    windows = [
        (
            rain.parse_timestamp(start),
            rain.parse_timestamp(end),
        )
        for start, end in rain.VALIDATION_WINDOWS
    ]

    result_rows = []
    prediction_rows = []
    fold_details = []
    skipped = []

    for end, samples in samples_by_interval.items():
        train = rain.training_before(samples, cutoff)

        test = [
            sample for sample in samples
            if sample["origin"] >= cutoff
        ]

        if len(train) < 40 or len(test) < 5:
            skipped.append({
                "interval_end_min": end,
                "reason": "Too few training or test rows",
            })
            continue

        validation_actual = []

        validation_probabilities = {
            method: [] for method in METHODS
        }

        used_folds = 0

        for fold_index, (left, right) in enumerate(windows, 1):
            fold_train = rain.training_before(train, left)

            validation = [
                sample for sample in train
                if left <= sample["origin"] < right
            ]

            if len(fold_train) < 20 or len(validation) < 5:
                continue

            probabilities, statuses = predict_methods(
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
                "train_samples": len(fold_train),
                "train_rainy_samples": sum(
                    sample["y"] for sample in fold_train
                ),
                "validation_samples": len(validation),
                "validation_rainy_samples": sum(
                    sample["y"] for sample in validation
                ),
                "model_status": statuses,
            })

            used_folds += 1

        if used_folds < 2:
            skipped.append({
                "interval_end_min": end,
                "reason": "Too few usable validation windows",
            })
            continue

        validation_metrics = {
            method: rain.calculate_metrics(
                validation_actual,
                validation_probabilities[method],
            )
            for method in METHODS
        }

        selected_method = min(
            METHODS,
            key=lambda method: (
                validation_metrics[method]["brier"]
            ),
        )

        probabilities, statuses = predict_methods(
            train,
            test,
        )

        probabilities["selected"] = probabilities[selected_method]

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
            "selected_method": selected_method,
            "local_status": statuses["logistic_local"],
            "neighbor_status": statuses["logistic_neighbors"],
            "test_mean_neighbor_coverage": float(
                np.mean([
                    sample["neighbor_x"][4]
                    for sample in test
                ])
            ),
        }

        for method in METHODS:
            row[f"validation_{method}_brier"] = (
                validation_metrics[method]["brier"]
            )

        for method, values in probabilities.items():
            metrics = rain.calculate_metrics(actual, values)

            for name, value in metrics.items():
                row[f"test_{method}_{name}"] = value

        result_rows.append(row)

        for index, sample in enumerate(test):
            prediction_rows.append({
                "station": sample["station"],
                "forecast_origin": sample["origin"].isoformat(),
                "interval_start": (
                    sample["end"] - rain.STEP
                ).isoformat(),
                "interval_end": sample["end"].isoformat(),
                "actual_rain": sample["y"],
                "neighbor_coverage": sample["neighbor_x"][4],
                "selected_method": selected_method,
                **{
                    f"{method}_probability": float(values[index])
                    for method, values in probabilities.items()
                },
            })

        print(
            f"Finished interval {end - 15}-{end} minutes",
            flush=True,
        )

    if not result_rows:
        raise ValueError(
            "No interval passed the sample coverage checks."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rain.write_csv(
        OUTPUT_DIR / "interval_metrics.csv",
        result_rows,
    )

    rain.write_csv(
        OUTPUT_DIR / "test_predictions.csv",
        prediction_rows,
    )

    neighbor_rows = [
        {
            "station": station,
            "neighbor": other,
            "distance_km": distance,
        }
        for station, items in sorted(neighbors.items())
        for other, distance in items
    ]

    rain.write_csv(
        OUTPUT_DIR / "station_neighbors.csv",
        neighbor_rows,
    )

    summary = {
        "holdout_start": cutoff.isoformat(),
        "neighbor_count": NEIGHBOR_COUNT,
        "maximum_distance_km": MAX_DISTANCE_KM,
        "maximum_neighbor_age_minutes": 15,
        "neighbor_feature_names": NEIGHBOR_FEATURE_NAMES,
        "classification_threshold": rain.CLASSIFICATION_THRESHOLD,
        "results": result_rows,
        "validation_details": fold_details,
        "skipped_intervals": skipped,
        "limitations": [
            "Snapshot station coordinates are assumed historically fixed.",
            "Historical station metadata availability was not reconstructed.",
            "All methods use identical complete-target evaluation rows.",
            "Neighbor readings must be available at forecast time.",
            "Imputation does not create new measurements.",
            "Nearby stations share weather events.",
            "Station-time samples are not independent trials.",
            "Parameters and the classification threshold are fixed.",
            "Reused holdout dates make this exploratory.",
            "Confirm results on later independent dates.",
            "Rain probabilities are not rainfall amounts or route-risk scores.",
            "The five-minute accumulation endpoint assumption is unchanged.",
        ],
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    def show(value):
        return "N/A" if value is None else f"{value:.3f}"

    print(
        "\nInterval  Rain  Frequency Brier  Local Brier  "
        "Neighbor Brier  Neighbor Recall  Neighbor AP"
    )

    for row in result_rows:
        print(
            f"{row['interval_start_min']:3d}-"
            f"{row['interval_end_min']:<3d} "
            f"{row['test_rainy_samples']:5d} "
            f"{row['test_training_frequency_brier']:15.4f} "
            f"{row['test_logistic_local_brier']:12.4f} "
            f"{row['test_logistic_neighbors_brier']:15.4f} "
            f"{show(row['test_logistic_neighbors_recall']):>16s} "
            f"{show(row['test_logistic_neighbors_average_precision']):>12s}"
        )

    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()