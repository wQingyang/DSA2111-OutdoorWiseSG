"""Compare recorded PM2.5 forecasts with persistence."""

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


# Repository paths
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
RESULTS = OUTPUT / "results"
FIGURES = OUTPUT / "figures"

EVALUATION = ROOT / "docs/forecast_evaluation.json"
MODEL = (
    ROOT
    / "prediction/results/pm25_multihorizon/backtest_models.json"
)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = json.loads(EVALUATION.read_text())

    # Check that the saved evaluation matches the supplied model and data.
    if file_hash(MODEL) != data["model_sha256"]:
        raise ValueError("Model file does not match the recorded evaluation.")

    for filename, expected_hash in data["dataset_sha256"].items():
        path = ROOT / "data/datasets/snapshot_20261015" / filename
        if file_hash(path) != expected_hash:
            raise ValueError(f"Dataset has changed: {filename}")

    models = json.loads(MODEL.read_text())

    # The evaluator's "frozen" output can depend on validation selection.
    # Only label the comparison Linear when all saved selections are linear.
    if not models or any(
        model["selected_using_validation"] != "linear"
        for model in models
    ):
        raise ValueError(
            "Not all frozen forecasts use linear models. "
            "Check the method labels before plotting."
        )

    rows = []

    for record in sorted(
        data["pm25"], key=lambda item: item["horizon_min"]
    ):
        rows.append({
            "horizon_min": record["horizon_min"],
            "test_samples": record["n"],
            "persistence_mae": record["persistence"]["mae_ug_m3"],
            "linear_mae": record["frozen"]["mae_ug_m3"],
            "persistence_rmse": record["persistence"]["rmse_ug_m3"],
            "linear_rmse": record["frozen"]["rmse_ug_m3"],
            "first_origin_sgt": record["first_origin"],
            "last_origin_sgt": record["last_origin"],
        })

    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    # Save full-precision values. Round only in the figure.
    csv_path = RESULTS / "pm25_metrics.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.7))

    positions = list(range(len(rows)))
    width = 0.34

    panels = [
        ("mae", "Mean absolute error"),
        ("rmse", "Root mean squared error"),
    ]

    methods = [
        ("persistence", "Persistence", "#929DA5", -width / 2),
        ("linear", "Frozen linear", "#24684C", width / 2),
    ]

    for ax, (metric, title) in zip(axes, panels):
        for method, label, colour, offset in methods:
            values = [row[f"{method}_{metric}"] for row in rows]

            bars = ax.bar(
                [position + offset for position in positions],
                values,
                width=width,
                label=label,
                color=colour,
                zorder=3,
            )

            ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=10)

        ax.set_xticks(
            positions,
            [
                f"{row['horizon_min']} min\nn = {row['test_samples']}"
                for row in rows
            ],
        )

        maximum = max(
            row[f"{method}_{metric}"]
            for row in rows
            for method in ("persistence", "linear")
        )

        ax.set_ylim(0, maximum * 1.22)
        ax.set_title(title, fontsize=14, pad=12)
        ax.set_ylabel(f"{metric.upper()} (µg/m³)")
        ax.set_xlabel("Forecast horizon and test samples", labelpad=10)
        ax.yaxis.grid(True, color="#E4E8E5")
        ax.set_axisbelow(True)

    fig.suptitle(
        "PM2.5 forecasting: linear model versus persistence",
        fontsize=17,
        y=0.98,
    )

    handles, labels = axes[0].get_legend_handles_labels()

    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=2,
        frameon=False,
    )

    fig.subplots_adjust(
        left=0.08,
        right=0.98,
        top=0.77,
        bottom=0.30,
        wspace=0.28,
    )

    fig.text(
        0.5,
        0.045,
        "Historical chronological holdout · five regions · lower errors are better\n"
        "Methods share test samples within each horizon; "
        "sample sets differ across horizons.",
        ha="center",
        va="bottom",
        fontsize=10,
        color="#505A54",
        linespacing=1.5,
    )

    for extension in ("png", "pdf"):
        fig.savefig(
            FIGURES / f"pm25_comparison.{extension}",
            dpi=220,
            facecolor="white",
        )

    plt.close(fig)

    print("\nPM2.5 comparison — errors in µg/m³")
    print("Values below: Persistence / Linear\n")

    for row in rows:
        print(
            f"{row['horizon_min']} min, "
            f"n={row['test_samples']}: "
            f"MAE {row['persistence_mae']:.3f} / "
            f"{row['linear_mae']:.3f}; "
            f"RMSE {row['persistence_rmse']:.3f} / "
            f"{row['linear_rmse']:.3f}"
        )

    print(f"\nMetrics: {csv_path}")
    print(f"Figures: {FIGURES}")


if __name__ == "__main__":
    main()