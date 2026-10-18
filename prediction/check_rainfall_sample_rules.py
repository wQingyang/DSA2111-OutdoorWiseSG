"""Compare strict and revised rainfall sample construction rules."""

from pathlib import Path
from datetime import timedelta
import json

import numpy as np

import train_rainfall_classification as rain


OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "results"
    / "rainfall_sample_rules"
)


def build_relaxed_samples(records):
    """Use recent inputs and distinguish rain evidence from missing data."""
    samples = {
        end: [] for end in rain.INTERVAL_ENDS
    }

    step = timedelta(minutes=15)
    five_minutes = timedelta(minutes=5)

    origin = min(records).replace(second=0, microsecond=0)
    origin = origin.replace(
        minute=(origin.minute // 15) * 15
    )

    final_origin = max(records) - step

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

        # Require a recent observation, not a complete 30-minute history.
        if (
            latest is None
            or not timedelta(0) <= origin - latest <= step
        ):
            origin += step
            continue

        value = records[latest]["value"]
        age_minutes = (origin - latest).total_seconds() / 60

        angle = (
            2 * np.pi
            * (origin.hour + origin.minute / 60)
            / 24
        )

        features = [
            value,
            age_minutes,
            float(np.sin(angle)),
            float(np.cos(angle)),
        ]

        for end in rain.INTERVAL_ENDS:
            interval_end = origin + timedelta(minutes=end)

            target_times = [
                interval_end - index * five_minutes
                for index in range(3)
            ]

            target_complete = all(
                time in records for time in target_times
            )

            positive_times = [
                time for time in target_times
                if time in records
                and records[time]["value"] > 0
            ]

            if positive_times:
                # One observed positive block proves rain occurrence.
                label = 1

                label_available_at = min(
                    records[time]["available_at"]
                    for time in positive_times
                )

            elif target_complete:
                # Dry requires all three observed blocks to be zero.
                label = 0

                label_available_at = max(
                    records[time]["available_at"]
                    for time in target_times
                )

            else:
                # Missing blocks plus observed zeros remain unknown.
                continue

            samples[end].append({
                "origin": origin,
                "end": interval_end,
                "label_available_at": label_available_at,
                "target_complete": target_complete,
                "x": features,
                "y": label,
                "persistence": float(value > 0),
            })

        origin += step

    return samples


def main():
    cutoff = rain.parse_timestamp(rain.HOLDOUT_START)
    stations = rain.load_stations()

    if not stations:
        raise ValueError("No usable rainfall observations.")

    comparison = {
        end: {
            "interval_start_min": end - 15,
            "interval_end_min": end,
            "strict_train_samples": 0,
            "strict_train_rain": 0,
            "revised_train_samples": 0,
            "revised_train_rain": 0,
            "strict_complete_test_samples": 0,
            "strict_complete_test_rain": 0,
            "revised_complete_test_samples": 0,
            "revised_complete_test_rain": 0,
        }
        for end in rain.INTERVAL_ENDS
    }

    for station, records in sorted(stations.items()):
        builders = [
            ("strict", rain.build_samples),
            ("revised", build_relaxed_samples),
        ]

        for name, builder in builders:
            samples_by_interval = builder(records)

            for end, samples in samples_by_interval.items():
                train = rain.training_before(samples, cutoff)

                # For evaluation coverage, require complete future targets.
                # This avoids retaining incomplete positive-only test labels.
                test = [
                    sample for sample in samples
                    if sample["origin"] >= cutoff
                    and sample.get("target_complete", True)
                ]

                row = comparison[end]

                row[f"{name}_train_samples"] += len(train)
                row[f"{name}_train_rain"] += sum(
                    sample["y"] for sample in train
                )

                row[f"{name}_complete_test_samples"] += len(test)
                row[f"{name}_complete_test_rain"] += sum(
                    sample["y"] for sample in test
                )

    rows = list(comparison.values())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rain.write_csv(
        OUTPUT_DIR / "sample_comparison.csv",
        rows,
    )

    summary = {
        "holdout_start": cutoff.isoformat(),
        "stations": len(stations),
        "comparison": rows,
        "limitations": [
            "Counts are station-interval pairs, not independent rain events.",
            "A positive observed block proves rain occurrence.",
            "Dry labels require complete observed zero coverage.",
            "Missing rainfall is never replaced with zero.",
            "Training may retain incomplete targets with positive evidence.",
            "Evaluation coverage requires complete future targets.",
            "Different input rules still change evaluation coverage.",
            "Compare future models on the same evaluation samples.",
            "Incomplete positive training targets can affect class proportions.",
            "Probability calibration needs separate validation.",
            "Five-minute accumulations are assumed to end at observed_at.",
        ],
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Interval  Training rain: strict -> revised  "
        "Complete test rain: strict -> revised"
    )

    for row in rows:
        print(
            f"{row['interval_start_min']:3d}-"
            f"{row['interval_end_min']:<3d} "
            f"{row['strict_train_rain']:15d} -> "
            f"{row['revised_train_rain']:<7d} "
            f"{row['strict_complete_test_rain']:12d} -> "
            f"{row['revised_complete_test_rain']}"
        )

    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()