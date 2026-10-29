"""Validate and analyse a saved route-mapping comparison and render its figures."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "analysis/station_matching/results/demo"
FIGURES = ROOT / "analysis/station_matching/figures"
STATION_METHODS = ("nearest_start", "nearest_end", "along_route_500m")
STATION_METRICS = ("rainfall", "wind_speed", "wind_direction", "air_temperature",
                   "relative_humidity", "wbgt", "heat_stress_level")
NUMERIC_COMPARISON_METRICS = ("rainfall", "wind_speed", "air_temperature", "relative_humidity", "wbgt")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_results(summary, samples):
    """Fail early if published totals or grouped summaries disagree with per-sample rows."""
    route_ids = {row["route_id"] for row in samples}
    if not samples or not summary:
        raise ValueError("Both comparison CSVs must contain data rows")
    as_of_values = {row["as_of"] for row in samples}
    if len(as_of_values) != 1:
        raise ValueError(f"Expected one assessment time in sample records, found {len(as_of_values)}")
    as_of = datetime.fromisoformat(next(iter(as_of_values)).replace("Z", "+00:00"))
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Assessment time in sample records must be timezone-aware")
    if len({row["source_kind"] for row in samples}) != 1:
        raise ValueError("Sample records contain more than one source kind")
    assert all(row["matched_location_type"] != "region" for row in samples if row["metric_class"] == "station")
    assert all(row["matched_location_type"] in ("", "region") for row in samples if row["metric_class"] == "region")
    assert all(row["freshness"] in {"fresh", "stale", "missing"} for row in samples)

    grouped = defaultdict(list)
    for row in samples:
        grouped[(row["route_id"], row["method"], row["metric"], row["metric_class"])].append(row)
    if len(grouped) != len(summary):
        raise ValueError("Summary and per-sample CSVs have different route/method/metric groups")
    for result in summary:
        key = (result["route_id"], result["method"], result["metric"], result["metric_class"])
        rows = grouped[key]
        matched = [row for row in rows if row["match_status"] == "matched"]
        fresh = [row for row in rows if row["freshness"] == "fresh"]
        stale = [row for row in rows if row["freshness"] == "stale"]
        distances = [float(row["distance_km"]) for row in matched if row["distance_km"]]
        values = [float(row["value"]) for row in matched if row["value"] not in ("", None)]
        expected = {
            "sample_count": len(rows), "matched_count": len(matched),
            "fresh_matched_count": len(fresh), "stale_matched_count": len(stale),
            "distinct_location_count": len({row["matched_location_id"] for row in matched}),
        }
        for field, value in expected.items():
            assert int(result[field]) == value, f"{key}: {field} disagrees with per-sample rows"
        for field, value in (("coverage_ratio", len(matched)/len(rows)),
                             ("fresh_coverage_ratio", len(fresh)/len(rows))):
            assert math.isclose(float(result[field]), value, abs_tol=1e-6), f"{key}: {field} mismatch"
        for field, value in (("mean_distance_km", statistics.mean(distances) if distances else None),
                             ("max_distance_km", max(distances) if distances else None),
                             ("mean_numeric_value", statistics.mean(values) if values else None),
                             ("max_numeric_value", max(values) if values else None)):
            actual = result[field]
            if value is None:
                assert actual == "", f"{key}: expected blank {field}"
            else:
                assert math.isclose(float(actual), value, abs_tol=1e-5), f"{key}: {field} mismatch"
    return next(iter(as_of_values))


def by_group(rows, *fields):
    output = defaultdict(list)
    for row in rows:
        output[tuple(row[field] for field in fields)].append(row)
    return output


def multi_station_matches(summary):
    return [row for row in summary if row["metric_class"] == "station"
            and row["method"] == "along_route_500m" and int(row["distinct_location_count"]) > 1]


def _route_geometry(route_id):
    json_path = ROOT / "data/catalog" / f"{route_id}.geojson"
    with json_path.open(encoding="utf-8") as handle:
        import json
        return json.load(handle)["geometry"]["coordinates"]


def make_rainfall_map(samples, assessment_time, output_path, data_mode_label):
    along = [row for row in samples if row["metric_class"] == "station" and
             row["method"] == "along_route_500m" and row["metric"] == "rainfall"]
    candidates = defaultdict(list)
    for row in along:
        if row["matched_location_id"]:
            candidates[row["route_id"]].append(row)
    eligible = [route_id for route_id, rows in candidates.items()
                if len({row["matched_location_id"] for row in rows}) > 1]
    if not eligible:
        raise ValueError("No route has multiple along-route rainfall station matches")
    bedok = "bedok_reservoir"
    bedok_station_count = len({row["matched_location_id"] for row in candidates.get(bedok, [])})
    route_id = bedok if bedok in eligible and bedok_station_count >= 3 else sorted(eligible)[0]
    along_rows = candidates[route_id]
    start = next(row for row in samples if row["route_id"] == route_id and row["method"] == "nearest_start"
                 and row["metric"] == "rainfall" and row["metric_class"] == "station")
    geometry = _route_geometry(route_id)
    fig, ax = plt.subplots(figsize=(10, 8))
    gx, gy = zip(*geometry)
    ax.plot(gx, gy, color="#253b64", linewidth=2.2, label="Route geometry", zorder=2)
    ax.scatter([row["sample_lon"] for row in along_rows], [row["sample_lat"] for row in along_rows],
               marker="o", s=26, facecolor="#f4a261", edgecolor="white", linewidth=.5,
               label="Along-route samples (~500 m)", zorder=4)
    ax.scatter([start["sample_lon"]], [start["sample_lat"]], marker="^", s=90,
               color="#2a9d8f", edgecolor="white", linewidth=.7, label="Start point", zorder=6)
    ax.scatter([geometry[-1][0]], [geometry[-1][1]], marker="s", s=55,
               color="#805ad5", edgecolor="white", linewidth=.6, label="Route end", zorder=5)

    # Keep all along-route sample-to-station lines visible, with a distinct start match.
    for index, row in enumerate(along_rows):
        ax.plot([float(row["sample_lon"]), float(row["matched_lon"])],
                [float(row["sample_lat"]), float(row["matched_lat"])],
                color="#e9a23b", alpha=.52, linewidth=.8, zorder=1,
                label="Along-route station matches" if index == 0 else "_nolegend_")
    start_matched = bool(start["matched_location_id"])
    if start_matched:
        ax.plot([float(start["sample_lon"]), float(start["matched_lon"])],
                [float(start["sample_lat"]), float(start["matched_lat"])],
                color="#d1495b", linewidth=2, linestyle="--", label="Start-point match", zorder=3)

    station_ids = sorted({row["matched_location_id"] for row in along_rows} |
                         ({start["matched_location_id"]} if start_matched else set()))
    station_rows = {row["matched_location_id"]: row for row in along_rows}
    if start_matched:
        station_rows[start["matched_location_id"]] = start
    colors = ["#0077b6", "#d00000", "#6a994e", "#8e44ad"]
    for index, location_id in enumerate(station_ids):
        row = station_rows[location_id]
        ax.scatter([float(row["matched_lon"])], [float(row["matched_lat"])], marker="*", s=190,
                   color=colors[index % len(colors)], edgecolor="black", linewidth=.5,
                   label=f"Station {location_id}", zorder=7)
        ax.annotate(location_id, (float(row["matched_lon"]), float(row["matched_lat"])),
                    xytext=(6, 6), textcoords="offset points", fontsize=9, weight="bold")
    ax.set_aspect(1 / math.cos(math.radians(statistics.mean(gy))))
    xpad = max((max(gx) - min(gx)) * .16, .004)
    ypad = max((max(gy) - min(gy)) * .18, .003)
    matched_rows = along_rows + ([start] if start_matched else [])
    ax.set_xlim(min(gx + tuple(float(row["matched_lon"]) for row in matched_rows)) - xpad,
                max(gx + tuple(float(row["matched_lon"]) for row in matched_rows)) + xpad)
    ax.set_ylim(min(gy + tuple(float(row["matched_lat"]) for row in matched_rows)) - ypad,
                max(gy + tuple(float(row["matched_lat"]) for row in matched_rows)) + ypad)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.grid(True, color="#cbd5e0", linewidth=.6, alpha=.7)
    handles, labels = ax.get_legend_handles_labels()
    # Put connection methods together in the legend, even though the many along-route
    # connections are drawn as individual line segments.
    ax.legend(handles, labels, loc="best", fontsize=8, framealpha=.95)
    ax.set_title(f"{data_mode_label} — rainfall matching: {start['route_name']}\n"
                 "Start point versus along-route samples (~500 m)", fontsize=13, pad=12)
    fig.subplots_adjust(bottom=.15, top=.88, left=.12, right=.98)
    fig.text(.5, .035, f"{data_mode_label} | Assessment: {assessment_time.replace('T', ' ')}",
             ha="center", fontsize=9)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return route_id


def make_distance_figure(summary, assessment_time, output_path, data_mode_label):
    route_ids = sorted({row["route_id"] for row in summary if row["metric_class"] == "station"})
    labels = {row["route_id"]: row["route_name"] for row in summary if row["metric_class"] == "station"}
    grouped = by_group([row for row in summary if row["metric_class"] == "station"], "route_id", "method")
    method_labels = {"nearest_start": "Start point", "nearest_end": "End point", "along_route_500m": "Along route (~500 m)"}
    colors = {"nearest_start": "#2a9d8f", "nearest_end": "#805ad5", "along_route_500m": "#e76f51"}
    fig, axes = plt.subplots(1, 2, figsize=(15, 9), sharey=True)
    y = np.arange(len(route_ids))
    bar_height = .23
    for panel, field, title in ((axes[0], "mean_distance_km", "Mean distance by route"),
                                (axes[1], "max_distance_km", "Maximum distance by route")):
        for offset, method in enumerate(STATION_METHODS):
            vals = []
            for route_id in route_ids:
                rows = grouped[(route_id, method)]
                numbers = [float(row[field]) for row in rows if row[field] != ""]
                vals.append(statistics.mean(numbers) if field == "mean_distance_km" else max(numbers))
            panel.barh(y + (offset-1)*bar_height, vals, height=bar_height*.9,
                       color=colors[method], label=method_labels[method])
        panel.set_title(title)
        panel.set_xlabel("Station-to-sample distance (km)")
        panel.grid(axis="x", alpha=.25)
        panel.invert_yaxis()
    axes[0].set_yticks(y, [labels[route_id] for route_id in route_ids])
    axes[1].tick_params(labelleft=False)
    axes[1].legend(loc="lower right", fontsize=9)
    fig.suptitle(f"{data_mode_label} — station matching distances\n"
                 "Route-level summaries across seven station-based metrics", fontsize=14)
    fig.subplots_adjust(left=.29, right=.98, bottom=.15, top=.86, wspace=.08)
    fig.text(.5, .06, "Start/end are single representative points; along-route uses route samples",
             ha="center", fontsize=8)
    fig.text(.5, .025, f"{data_mode_label} | Assessment: {assessment_time.replace('T', ' ')}",
             ha="center", fontsize=9)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_freshness_figure(summary, assessment_time, output_path, data_mode_label):
    rows = [row for row in summary if row["metric_class"] == "station" and row["method"] == "along_route_500m"]
    route_ids = sorted({row["route_id"] for row in rows})
    route_names = {row["route_id"]: row["route_name"] for row in rows}
    metrics = [metric for metric in STATION_METRICS if any(row["metric"] == metric for row in rows)]
    lookup = {(row["route_id"], row["metric"]): float(row["fresh_coverage_ratio"]) for row in rows}
    matrix = np.array([[lookup[(route_id, metric)] for metric in metrics] for route_id in route_ids])
    fig, ax = plt.subplots(figsize=(12, 8))
    image = ax.imshow(matrix * 100, aspect="auto", cmap="YlGnBu", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(metrics)), [metric.replace("_", " ").title() for metric in metrics], rotation=28, ha="right")
    ax.set_yticks(np.arange(len(route_ids)), [route_names[route_id] for route_id in route_ids])
    ax.set_title(f"{data_mode_label} — along-route fresh coverage by route and metric\n"
                 "Fresh matched samples ÷ all along-route samples", fontsize=13, pad=12)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            color = "white" if matrix[i, j] >= .55 else "#1a202c"
            ax.text(j, i, f"{matrix[i, j]*100:.0f}%", ha="center", va="center", color=color, fontsize=8)
    colorbar = fig.colorbar(image, ax=ax, pad=.02)
    colorbar.set_label("Fresh coverage (%)")
    fig.subplots_adjust(left=.30, right=.92, bottom=.25, top=.86)
    fig.text(.5, .055, "Fresh coverage is separate from spatial match coverage",
             ha="center", fontsize=8)
    fig.text(.5, .025, f"{data_mode_label} | Assessment: {assessment_time.replace('T', ' ')}",
             ha="center", fontsize=9)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_analysis(summary, samples, assessment_time, output_path, data_mode_label, reproduction_command):
    multi = multi_station_matches(summary)
    routes = defaultdict(dict)
    for row in multi:
        routes[row["route_id"]][row["metric"]] = row
    station_summary = [row for row in summary if row["metric_class"] == "station"]
    station_samples = [row for row in samples if row["metric_class"] == "station"]
    regional_samples = [row for row in samples if row["metric_class"] == "region"]
    source_kind = ", ".join(sorted({row["source_kind"] for row in samples}))
    route_names = {row["route_id"]: row["route_name"] for row in station_summary}
    method_distance = {}
    for method in STATION_METHODS:
        rows = [row for row in station_summary if row["method"] == method]
        mean_distance = statistics.mean(float(row["mean_distance_km"]) for row in rows if row["mean_distance_km"])
        max_distance = max(float(row["max_distance_km"]) for row in rows if row["max_distance_km"])
        method_distance[method] = (mean_distance, max_distance)

    lookup = {(row["route_id"], row["metric"], row["method"]): row for row in station_summary}
    comparisons = []
    for route_id in sorted({row["route_id"] for row in station_summary}):
        for metric in NUMERIC_COMPARISON_METRICS:
            start = lookup[(route_id, metric, "nearest_start")]
            end = lookup[(route_id, metric, "nearest_end")]
            along = lookup[(route_id, metric, "along_route_500m")]
            if all(row["mean_numeric_value"] != "" for row in (start, end, along)):
                comparisons.append((route_id, metric, float(start["mean_numeric_value"]),
                                    float(end["mean_numeric_value"]), float(along["mean_numeric_value"]),
                                    float(along["max_numeric_value"])))
    start_end_equal = sum(math.isclose(row[2], row[3], abs_tol=1e-9) for row in comparisons)
    along_diff = [row for row in comparisons if not math.isclose(row[2], row[4], abs_tol=1e-9)]
    matched_rain = [float(row["value"]) for row in station_samples
                    if row["metric"] == "rainfall" and row["match_status"] == "matched"
                    and row["value"] not in ("", None)]
    all_rain_zero = bool(matched_rain) and all(math.isclose(value, 0, abs_tol=1e-12) for value in matched_rain)

    multi_lines = []
    for route_id, metrics in sorted(routes.items()):
        names = ", ".join(metric.replace("_", " ") for metric in STATION_METRICS if metric in metrics)
        station_names = sorted({row["matched_location_id"] for row in samples
                                if row["route_id"] == route_id and row["method"] == "along_route_500m"
                                and row["metric"] == "rainfall" and row["matched_location_id"]})
        station_count = max(int(row["distinct_location_count"]) for row in metrics.values())
        multi_lines.append(f"| {route_names[route_id]} | {names} | {station_count} | {', '.join(station_names) or 'None'} |")

    distance_lines = []
    for method, label in (("nearest_start", "Nearest start"), ("nearest_end", "Nearest end"),
                          ("along_route_500m", "Along route (~500 m)")):
        mean_distance, max_distance = method_distance[method]
        distance_lines.append(f"| {label} | {mean_distance:.3f} | {max_distance:.3f} |")

    difference_lines = []
    for route_id, metric, start, end, along_mean, along_max in along_diff:
        route_name = lookup[(route_id, metric, "nearest_start")]["route_name"]
        difference_lines.append(f"| {route_name} | {metric.replace('_', ' ')} | {start:g} | {end:g} | {along_mean:.6g} | {along_max:g} |")
    difference_table = "\n".join(difference_lines) if difference_lines else "No numeric value differences were found."

    coverage_lines = []
    for method in STATION_METHODS:
        rows = [row for row in station_samples if row["method"] == method]
        matched = sum(row["match_status"] == "matched" for row in rows)
        fresh = sum(row["freshness"] == "fresh" for row in rows)
        missing = sum(row["freshness"] == "missing" or row["match_status"] == "missing" for row in rows)
        coverage_lines.append(
            f"| {method} | {matched}/{len(rows)} ({matched/len(rows):.1%}) | "
            f"{fresh}/{len(rows)} ({fresh/len(rows):.1%}) | {missing} |"
        )
    along_summaries = [row for row in station_summary if row["method"] == "along_route_500m"]
    along_mean_spatial = statistics.mean(float(row["coverage_ratio"]) for row in along_summaries)
    along_mean_fresh = statistics.mean(float(row["fresh_coverage_ratio"]) for row in along_summaries)
    along_counts = Counter(row["freshness"] for row in station_samples if row["method"] == "along_route_500m")
    spatial_all = sum(row["match_status"] == "matched" for row in station_samples)
    spatial_ratio_all = spatial_all / len(station_samples)
    regional_states = Counter(row["freshness"] for row in regional_samples)
    regional_state_text = (f"fresh {regional_states['fresh']}, stale {regional_states['stale']}, "
                           f"missing {regional_states['missing']}")
    multi_detail = "; ".join(
        f"{route_names[route_id]} ({', '.join(metric.replace('_', ' ') for metric in STATION_METRICS if metric in metrics)})"
        for route_id, metrics in sorted(routes.items())
    ) or "None in this snapshot"
    rain_note = (
        "All matched rainfall values are zero in this snapshot, so rainfall-value differences cannot be demonstrated."
        if all_rain_zero else
        f"Matched rainfall values span {min(matched_rain):g} to {max(matched_rain):g}; this describes this saved snapshot only."
        if matched_rain else
        "No numeric rainfall observations were matched, so rainfall-value differences cannot be demonstrated."
    )

    text = f"""# Mapping experiment analysis

## Verification and scope

The saved CSVs agree: **{len(samples):,} per-sample rows**, **{len(summary):,} summary rows**, and **{len({row['route_id'] for row in samples})} routes**. They contain **{len(station_samples):,} station sample rows** and **{len(regional_samples):,} separate regional assignment rows**. Grouped match, freshness, distance, and numeric-value fields in `summary.csv` were recomputed from `per_sample.csv` and verified.

Dataset label: **{data_mode_label}** (`source_kind={source_kind}`). The assessment time from the sample records is **{assessment_time}**. Regional PM2.5, PSI and PM10 assignments are excluded from station analyses below.

## Reproduction

From the repository root, regenerate this analysis and its figures using the saved CSVs:

```bash
{reproduction_command}
```

## Routes and metrics matching multiple stations

Along-route matching found more than one distinct station on these routes and station-based metrics:

| Route | Station-based metrics with multiple stations | Maximum distinct stations for a metric | Rainfall sample station IDs |
|---|---|---:|---|
{chr(10).join(multi_lines)}

Qualifying route/metric pairs: **{len(multi)}**. The rainfall map selects Bedok Reservoir when its along-route rainfall records contain at least three distinct stations; otherwise it selects a route confirmed by the sample rows to have multiple rainfall stations. It displays route geometry, start/end, sample points, stations, and matching lines on a shared extent.

## Station matching distances

These distances summarize station-to-sample separation. Mean distance averages the route/metric mean distances per method; maximum is the largest route/metric sample distance:

| Method | Mean distance (km) | Maximum distance (km) |
|---|---:|---:|
{chr(10).join(distance_lines)}

Start-point and end-point coverage concerns only each method's single representative point per route and metric. It is not equivalent to whole-route sample coverage. Spatial coverage means a usable station was found within the configured limit; fresh coverage counts only matched samples whose observation passed the freshness threshold.

| Method | Spatial matches | Fresh matches | Missing samples |
|---|---:|---:|---:|
{chr(10).join(coverage_lines)}

Along-route mean spatial coverage across route/metric summaries was **{along_mean_spatial:.1%}**, while mean fresh coverage was **{along_mean_fresh:.1%}**. Across all station samples, spatial coverage was **{spatial_ratio_all:.1%}**. Freshness states for along-route samples: fresh {along_counts['fresh']}, stale {along_counts['stale']}, missing {along_counts['missing']}. A smaller station distance does not prove greater measurement accuracy or representativeness.

## Matched numeric values

Wind direction was excluded from arithmetic comparisons because angles wrap around at 360°. Heat-stress level is categorical and has no numeric value. Across {len(comparisons)} complete route/metric numeric comparisons, start and end values agreed in **{start_end_equal}** cases. Along-route matched-sample means differed from the start-point values in **{len(along_diff)}** cases. {rain_note}

| Route | Metric | Start value | End value | Along-route matched-sample mean | Along-route matched-sample maximum |
|---|---|---:|---:|---:|---:|
{difference_table}

Along-route means and maxima summarize values attached to matched samples. They are not ground-truth measurements along the route or interpolated estimates. A station can be assigned to many nearby samples, so sample assignments are not independent observations. Regional metrics are kept separate and are not part of numeric station comparisons.

## Freshness and interpretation limits

Regional assignment states, kept separately from station results: {regional_state_text}. {data_mode_label} results establish that the methods can produce matches for this saved snapshot. They do not establish measurement accuracy, live coverage beyond the recorded snapshot, or route safety.

Freshness depends on saved timestamps and configured source-specific age thresholds at the assessment time. The experiment does not establish that a geographically nearest station represents conditions at a route sample. Routes/metrics with multiple stations in this snapshot: {multi_detail}.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RESULTS,
                        help="Directory containing summary.csv and per_sample.csv (default: demo results)")
    parser.add_argument("--output-dir", type=Path,
                        help="Directory for analysis.md; defaults to the input directory")
    parser.add_argument("--summary", type=Path, help="Optional explicit summary CSV path")
    parser.add_argument("--samples", type=Path, help="Optional explicit per-sample CSV path")
    parser.add_argument("--figures-dir", type=Path, default=FIGURES)
    parser.add_argument("--analysis", type=Path, help="Optional explicit analysis Markdown path")
    parser.add_argument("--data-mode-label", help="Figure/report label, e.g. 'Live observations'")
    parser.add_argument("--figure-prefix", help="Output figure filename prefix; defaults to demo or label")
    args = parser.parse_args()
    summary_path = args.summary or args.input_dir / "summary.csv"
    samples_path = args.samples or args.input_dir / "per_sample.csv"
    output_dir = args.output_dir or args.input_dir
    analysis_path = args.analysis or output_dir / "analysis.md"
    data_mode_label = args.data_mode_label or "Synthetic demo data"
    default_prefix = "demo" if args.data_mode_label is None else args.data_mode_label.lower().split()[0]
    figure_prefix = args.figure_prefix or default_prefix
    summary, samples = read_csv(summary_path), read_csv(samples_path)
    assessment_time = verify_results(summary, samples)
    args.figures_dir.mkdir(parents=True, exist_ok=True)
    route_id = make_rainfall_map(samples, assessment_time,
                                 args.figures_dir / f"{figure_prefix}-rainfall-matching-map.png", data_mode_label)
    make_distance_figure(summary, assessment_time,
                         args.figures_dir / f"{figure_prefix}-rainfall-station-distance.png", data_mode_label)
    make_freshness_figure(summary, assessment_time,
                          args.figures_dir / f"{figure_prefix}-fresh-coverage.png", data_mode_label)
    reproduction_command = (
        f"MPLCONFIGDIR=/tmp/outdoorwise-mpl-config MPLBACKEND=Agg .venv/bin/python analysis/station_matching/scripts/analyze_route_mapping.py "
        f"--input-dir {args.input_dir} --output-dir {output_dir} --figures-dir {args.figures_dir} "
        f"--data-mode-label \"{data_mode_label}\" --figure-prefix {figure_prefix}"
    )
    render_analysis(summary, samples, assessment_time, analysis_path,
                    data_mode_label, reproduction_command)
    print(f"Verified {len(samples)} sample rows and {len(summary)} summary rows.")
    print(f"Assessment time: {assessment_time}; source_kind={samples[0]['source_kind']}.")
    print(f"Rainfall map route: {route_id}; wrote {analysis_path} and three figures to {args.figures_dir}.")


if __name__ == "__main__":
    main()
