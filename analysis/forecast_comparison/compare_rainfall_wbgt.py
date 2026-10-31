import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT / "prediction"))

import train_rainfall_classification as rain
import train_rainfall_neighbors as neighbors
import train_wbgt_multihorizon as heat


HORIZONS = [15, 30, 60]
COLORS = ["#929DA5", "#DBA44D", "#548CB0", "#24684C"]


def read_csv(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def value(row, key):
    if row[key] in ("", "None", "null"):
        return np.nan
    return float(row[key])


def save_plot(fig, folder, name):
    folder.mkdir(parents=True, exist_ok=True)

    for extension in ("png", "pdf"):
        fig.savefig(
            folder / f"{name}.{extension}",
            dpi=220,
            facecolor="white",
        )

    plt.close(fig)


def grouped(
    ax,
    rows,
    methods,
    field,
    labels,
    title,
    ylabel,
    probability=False,
):
    x = np.arange(len(rows))
    width = 0.75 / len(methods)
    maxima = []

    palette = (
        ["#929DA5", "#24684C"]
        if len(methods) == 2
        else COLORS
    )

    for index, (method, label) in enumerate(methods):
        y = [
            value(row, field.format(method=method))
            for row in rows
        ]

        positions = x + (
            index - (len(methods) - 1) / 2
        ) * width

        bars = ax.bar(
            positions,
            y,
            width,
            label=label,
            color=palette[index],
            zorder=3,
        )

        for position, number, bar in zip(positions, y, bars):
            if np.isfinite(number):
                maxima.append(number)

                ax.annotate(
                    f"{number:.3f}",
                    (position, number),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    rotation=90,
                )
            else:
                ax.text(
                    position,
                    0.02,
                    "N/A",
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    fontsize=8,
                    rotation=90,
                )

    ax.set_xticks(x, labels)
    ax.set_title(title, fontsize=13, pad=12)
    ax.set_ylabel(ylabel)

    upper = 1.12 if probability else (
        max(maxima or [1]) * 1.4 or 1
    )
    ax.set_ylim(0, upper)

    if probability:
        ax.set_yticks(np.arange(0, 1.01, 0.2))

    ax.yaxis.grid(True, color="#E4E8E5")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def compare_rainfall(output):
    print(
        "Running rainfall comparison with chronological validation...",
        flush=True,
    )

    # Change settings only inside this process.
    # Original research source files are not edited.
    previous_horizons = rain.INTERVAL_ENDS
    previous_output = neighbors.OUTPUT_DIR

    rain.INTERVAL_ENDS = HORIZONS
    neighbors.OUTPUT_DIR = output / "results/rainfall"

    try:
        neighbors.main()
    finally:
        rain.INTERVAL_ENDS = previous_horizons
        neighbors.OUTPUT_DIR = previous_output

    rows = read_csv(
        output / "results/rainfall/interval_metrics.csv"
    )
    rows.sort(key=lambda row: int(row["interval_end_min"]))

    methods = [
        ("always_dry", "Always dry"),
        ("persistence", "Persistence"),
        ("logistic_local", "Local logistic"),
        ("logistic_neighbors", "Neighbour logistic"),
    ]

    labels = [
        f"{r['interval_start_min']}–"
        f"{r['interval_end_min']} min\n"
        f"n={r['test_samples']}\n"
        f"rain={r['test_rainy_samples']}"
        for r in rows
    ]

    # Do not mislabel a prior fallback as a fitted classifier.
    if any(
        r["local_status"] != "logistic_regression"
        for r in rows
    ):
        methods[2] = (
            "logistic_local",
            "Local logistic / prior fallback",
        )

    if any(
        r["neighbor_status"] != "logistic_regression"
        for r in rows
    ):
        methods[3] = (
            "logistic_neighbors",
            "Neighbour logistic / prior fallback",
        )

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))

    panels = [
        (
            "brier",
            "Brier score — lower is better",
            "Brier score",
        ),
        (
            "average_precision",
            "Average precision — higher is better",
            "Average precision",
        ),
        (
            "recall",
            "Recall at threshold 0.5",
            "Recall",
        ),
    ]

    for ax, (metric, title, ylabel) in zip(axes, panels):
        grouped(
            ax,
            rows,
            methods,
            "test_{method}_" + metric,
            labels,
            title,
            ylabel,
            probability=metric != "brier",
        )
        ax.set_xlabel(
            "Future 15-minute target interval",
            labelpad=10,
        )

    fig.suptitle(
        "Rainfall event prediction: matched-sample model comparison",
        fontsize=18,
        y=0.98,
    )

    handles, legend_labels = axes[0].get_legend_handles_labels()

    fig.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=2,
        frameon=False,
    )

    fig.subplots_adjust(
        left=0.06,
        right=0.98,
        top=0.73,
        bottom=0.34,
        wspace=0.32,
    )

    fig.text(
        0.5,
        0.04,
        "Same complete-target test rows for all methods within each interval.\n"
        "N/A means undefined, not zero. "
        "All-dry targets cannot establish rain-detection skill.\n"
        "Intervals are separate: 45–60 min is not cumulative rain "
        "during the first hour.",
        ha="center",
        fontsize=10,
        color="#505A54",
        linespacing=1.5,
    )

    save_plot(
        fig,
        output / "figures",
        "rainfall_comparison",
    )


def compare_wbgt(output):
    print(
        "Running WBGT comparison with chronological validation...",
        flush=True,
    )

    previous_horizons = heat.HORIZONS
    previous_output = heat.OUTPUT_DIR

    heat.HORIZONS = HORIZONS
    heat.OUTPUT_DIR = output / "results/wbgt"

    try:
        heat.main()
    finally:
        heat.HORIZONS = previous_horizons
        heat.OUTPUT_DIR = previous_output

    rows = read_csv(
        output / "results/wbgt/horizon_metrics.csv"
    )
    rows.sort(key=lambda row: int(row["horizon_min"]))

    methods = [
        ("baseline", "Persistence"),
        ("linear", "Linear"),
    ]

    labels = [
        f"{r['horizon_min']} min\n"
        f"n={r['station_time_pairs']}\n"
        f"stations={r['stations_evaluated']}"
        for r in rows
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))

    for ax, metric, title in zip(
        axes,
        ["mae", "rmse"],
        ["Mean absolute error", "Root mean squared error"],
    ):
        grouped(
            ax,
            rows,
            methods,
            "{method}_" + metric + "_degC",
            labels,
            title,
            metric.upper() + " (°C)",
        )
        ax.set_xlabel(
            "Forecast horizon and test samples",
            labelpad=10,
        )

    fig.suptitle(
        "WBGT forecasting: linear model versus persistence",
        fontsize=18,
        y=0.98,
    )

    handles, legend_labels = axes[0].get_legend_handles_labels()

    fig.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=2,
        frameon=False,
    )

    fig.subplots_adjust(
        left=0.08,
        right=0.98,
        top=0.77,
        bottom=0.34,
        wspace=0.30,
    )

    fig.text(
        0.5,
        0.045,
        "Exploratory chronological holdout · lower errors are better\n"
        "Methods share test samples within each horizon; "
        "sample sets may differ across horizons.",
        ha="center",
        fontsize=10,
        color="#505A54",
        linespacing=1.5,
    )

    save_plot(
        fig,
        output / "figures",
        "wbgt_comparison",
    )


def protected_hashes():
    paths = list(
        (ROOT / "data/datasets/snapshot_20261015").glob("*.csv")
    )
    paths += list((ROOT / "prediction").glob("*.py"))
    paths += [
        ROOT / "prediction/results/pm25_multihorizon/backtest_models.json",
        ROOT / "docs/forecast_evaluation.json",
    ]

    return {
        str(path.relative_to(ROOT)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in paths
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=["rainfall", "wbgt", "all"],
        default="all",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE,
    )
    args = parser.parse_args()

    output = args.output_dir.resolve()
    before = protected_hashes()

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
    })

    if args.task in ("rainfall", "all"):
        compare_rainfall(output)

    if args.task in ("wbgt", "all"):
        compare_wbgt(output)

    if protected_hashes() != before:
        raise RuntimeError(
            "A protected source file changed during analysis."
        )

    (output / "results").mkdir(
        parents=True,
        exist_ok=True,
    )

    verification = {
        "task": args.task,
        "input_sha256": before,
        "protected_inputs_unchanged": True,
        "holdout_start_sgt": rain.HOLDOUT_START,
        "selected_horizons_min": HORIZONS,
        "limitations": [
            "Exploratory reused holdout; "
            "no new independent evaluation period.",
            "Rainfall uses recent-input, complete-target samples "
            "from the neighbour experiment, "
            "not the strict baseline sample set.",
            "Models use identical test rows within each "
            "interval/horizon.",
            "Single-class test targets cannot establish "
            "rain-detection skill.",
            "No model is installed into the application "
            "by this script.",
        ],
    }

    verification_path = (
        output / "results"
        / f"{args.task}_verification.json"
    )
    verification_path.write_text(
        json.dumps(verification, indent=2) + "\n"
    )

    print(f"\nDone. Results: {output / 'results'}")
    print(f"Figures: {output / 'figures'}")


if __name__ == "__main__":
    main()