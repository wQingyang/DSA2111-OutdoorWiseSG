"""Reproduce the offline freshness analysis without importing the application."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
from statistics import fmean, median
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
import tomllib

# Keep Matplotlib's cache outside the repository and avoid GUI/network activity.
_CACHE = tempfile.TemporaryDirectory(prefix="outdoorwise-freshness-")
os.environ["MPLCONFIGDIR"] = _CACHE.name
os.environ["XDG_CACHE_HOME"] = _CACHE.name
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator

if __package__:
    from .session_audit import evaluate_source, read_runs
else:
    from session_audit import evaluate_source, read_runs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SGT = ZoneInfo("Asia/Singapore")
SOURCES = {
    "Rainfall": ("weather", "rainfall", "nea_rainfall"),
    "WBGT": ("heat_stress", "wbgt", "nea_wbgt"),
    "PM2.5": ("air_quality", "pm25", "nea_pm25"),
    "PSI": ("air_quality", "psi", "nea_psi"),
}
# Rounded collection-group results from the preceding read-only audit.
AUDIT = {
    "Rainfall": (145782, 1643, 9.10, 9.39, 11.18, 379.03, 9.47),
    "WBGT": (19080, 636, 17.00, 17.38, 23.82, 25.22, 17.00),
    "PM2.5": (990, 198, 10.40, 12.27, 24.42, 58.67, 52.36),
    "PSI": (990, 198, 10.22, 12.41, 26.21, 56.43, 52.52),
}
FIELDS = ["source", "valid_first_collection_records", "distinct_fetch_timestamp_groups",
          "median_observation_age_minutes", "mean_observation_age_minutes",
          "p90_observation_age_minutes", "maximum_observation_age_minutes",
          "median_latest_retained_fetch_age_minutes"]
CADENCE_GAP_LIMIT_MINUTES = 120
OFFICIAL = {
    "Rainfall": (5, 5, "5-minute total (collector/payload contract)"),
    "WBGT": (15, 15, "15-minute average"),
    "PM2.5": (15, 60, "1-hour average"),
    "PSI": (15, 60, "rolling 24-hour index; hourly readings"),
}
CADENCE_FIELDS = ["official_dataset_update_minutes", "measurement_definition",
                  "configured_polling_minutes", "observed_interval_median_minutes",
                  "observed_interval_mode_minutes", "observed_interval_p90_minutes",
                  "observed_intervals_retained", "observed_intervals_excluded_over_120_minutes",
                  "provider_update_interval_median_minutes", "provider_update_interval_mode_minutes",
                  "provider_update_interval_p90_minutes", "provider_delay_valid_first_records",
                  "provider_delay_fetch_groups", "provider_delay_median_minutes",
                  "provider_delay_p90_minutes", "provider_delay_maximum_minutes",
                  "missing_provider_update_first_records", "negative_provider_delay_first_records",
                  "provider_delay_interpretation"]
SESSION_FIELDS = ["active_first_fetch_groups", "active_median_age_minutes", "active_mean_age_minutes",
                  "active_p90_age_minutes", "active_maximum_age_minutes", "post_gap_first_fetch_groups",
                  "other_uncertain_first_fetch_groups", "qualifying_active_successful_runs",
                  "runs_demonstrably_over_60_minutes", "maximum_demonstrated_age_lower_bound_minutes"]
# Independent numerical checkpoints from the completed read-only inactivity audit.
SESSION_AUDIT = {
    "Rainfall": (1552, 9.08, 1755, 16, 46, 45),
    "WBGT": (555, 16.88, 558, 0, 18, 63),
    "PM2.5": (158, 9.19, 598, 13, 15, 25),
    "PSI": (157, 9.50, 594, 12, 17, 24),
}
FIGURE_START = datetime(2026, 10, 8, tzinfo=SGT)
FIGURE_END_EXCLUSIVE = datetime(2026, 10, 18, tzinfo=SGT)
SOURCE_COLORS = {"Rainfall": "#0072B2", "WBGT": "#D55E00",
                 "PM2.5": "#009E73", "PSI": "#8255A5"}
PANEL_OBSERVATIONS = {"Rainfall": "5-min observations", "WBGT": "15-min observations",
                      "PM2.5": "Hourly observations", "PSI": "Hourly observations"}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def csv_time(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
        raise ValueError(f"Expected Singapore-local CSV v3 timestamp: {value!r}")
    return datetime.fromisoformat(value).replace(tzinfo=SGT)


def read_groups(path, metric, source, first):
    groups = defaultdict(list)
    keys = set()
    count = fetch_changed = 0
    revisions = defaultdict(int)
    earliest = latest = None
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), 2):
            if row["source_kind"] != "live" or row["metric"] != metric:
                continue
            if first and int(row["revision"]) != 1:
                continue
            if row["source"] != source:
                raise ValueError(f"Unexpected source at {path}:{line}")
            try:
                observed = csv_time(row["observed_at"])
                fetched = csv_time(row["fetched_at"])
                age = (fetched - observed).total_seconds() / 60
            except ValueError as exc:
                raise ValueError(f"Invalid timestamp at {path}:{line}") from exc
            if not math.isfinite(age) or age < 0:
                raise ValueError(f"Invalid/negative observation age at {path}:{line}")
            key = tuple(row[k] for k in ("source", "location_id", "observed_at",
                        "metric", "aggregation_window", "source_kind"))
            if key in keys:
                raise ValueError(f"Duplicate observation key at {path}:{line}")
            keys.add(key)
            if first and row["first_fetched_at"] != row["fetched_at"]:
                raise ValueError(f"Revision-1 first/fetch mismatch at {path}:{line}")
            groups[fetched].append(age)
            count += 1
            fetch_changed += row["fetched_at"] != row["first_fetched_at"]
            revisions[row["revision"]] += 1
            earliest = observed if earliest is None else min(earliest, observed)
            latest = observed if latest is None else max(latest, observed)
    if not groups:
        raise ValueError(f"No eligible observations in {path}")
    points = sorted((time, median(ages)) for time, ages in groups.items())
    details = dict(valid_records=count, fetch_timestamp_groups=len(groups),
                   observation_start=earliest.isoformat(), observation_end=latest.isoformat(),
                   collection_start=points[0][0].isoformat(), collection_end=points[-1][0].isoformat(),
                   negative_ages=0, invalid_ages=0, duplicate_keys=0,
                   fetched_differs_from_first_fetched_records=fetch_changed,
                   revisions=dict(sorted(revisions.items())),
                   minimum_group_records=min(map(len, groups.values())),
                   maximum_group_records=max(map(len, groups.values())))
    return points, details


def statistics(points):
    ages = sorted(age for _, age in points)
    index = (len(ages) - 1) * 0.9
    low = math.floor(index)
    p90 = ages[low] + (ages[min(low + 1, len(ages) - 1)] - ages[low]) * (index - low)
    return median(ages), fmean(ages), p90, max(ages)


def describe(values):
    """Describe exact recorded values, retaining all tied modes without binning."""
    if not values:
        return dict(n=0, median=None, mean=None, mode=[], mode_count=0, p90=None, maximum=None)
    mid, mean, p90, maximum = statistics(list(enumerate(values)))
    counts = Counter(values)
    frequency = max(counts.values())
    return dict(n=len(values), median=mid, mean=mean, p90=p90, maximum=maximum,
                mode=sorted(value for value, count in counts.items() if count == frequency),
                mode_count=frequency)


def interval_distribution(timestamps, limit=CADENCE_GAP_LIMIT_MINUTES):
    """Screen only cadence intervals, never remove ages or collection points."""
    unique = sorted(set(timestamps))
    seconds = [(right-left).total_seconds() for left, right in zip(unique, unique[1:])]
    kept = [value/60 for value in seconds if value <= limit*60]
    return dict(unique_timestamps=len(unique), cutoff_minutes=limit,
                all_intervals=describe([value/60 for value in seconds]),
                typical_intervals=describe(kept), excluded_intervals=sum(value > limit*60 for value in seconds),
                histogram_seconds=dict(sorted(Counter(seconds).items())))


def history_diagnostics(path, metric, source, expected_observation_minutes):
    """Use all retained revisions for cadence, revision 1 for acquisition offsets."""
    times = {"observed_at": set(), "source_updated_at": set()}
    per_key = defaultdict(list)
    delays = defaultdict(list)
    counters = Counter()
    first_delay_values = []
    first_age_values = []
    update_observation_pairs = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["source_kind"] != "live" or row["metric"] != metric:
                continue
            if row["source"] != source:
                raise ValueError(f"Unexpected source in {path}")
            observed, fetched = csv_time(row["observed_at"]), csv_time(row["fetched_at"])
            updated = csv_time(row["source_updated_at"]) if row["source_updated_at"] else None
            times["observed_at"].add(observed)
            counters["all_revision_records"] += 1
            if updated is not None:
                times["source_updated_at"].add(updated)
                update_observation_pairs[updated].add(observed)
            else:
                counters["missing_provider_update_all_records"] += 1
            per_key[(row["location_id"], observed, row["aggregation_window"])].append(row)
            if int(row["revision"]) != 1:
                continue
            counters["first_records"] += 1
            first_age_values.append((fetched-observed).total_seconds()/60)
            if updated is None:
                counters["missing_provider_update_first_records"] += 1
                continue
            value = (fetched-updated).total_seconds()/60
            first_delay_values.append(value)
            delays[fetched].append(value)
            counters["negative_provider_delay_first_records"] += value < 0
            counters["provider_update_before_observation_first_records"] += updated < observed
    measurement_fields = ("value", "category_value", "unit", "aggregation_window", "raw_value", "raw_unit")
    for rows in per_key.values():
        rows.sort(key=lambda row: int(row["revision"]))
        for earlier, later in zip(rows, rows[1:]):
            counters["revision_transitions"] += 1
            update_changed = earlier["source_updated_at"] != later["source_updated_at"]
            measurement_changed = any(earlier[k] != later[k] for k in measurement_fields)
            counters["update_only_revision_transitions"] += update_changed and not measurement_changed
            counters["measurement_changed_revision_transitions"] += measurement_changed
            counters["backwards_provider_update_revision_transitions"] += bool(
                earlier["source_updated_at"] and later["source_updated_at"] and
                csv_time(later["source_updated_at"]) < csv_time(earlier["source_updated_at"]))
    cadence = {field: interval_distribution(values) for field, values in times.items()}
    phase_seconds = expected_observation_minutes*60
    aligned = sum((time.hour*3600+time.minute*60+time.second) % phase_seconds == 0
                  for time in times["observed_at"])
    counts = {key: counters[key] for key in (
        "all_revision_records", "first_records", "missing_provider_update_all_records",
        "missing_provider_update_first_records", "negative_provider_delay_first_records",
        "provider_update_before_observation_first_records", "revision_transitions",
        "update_only_revision_transitions", "measurement_changed_revision_transitions",
        "backwards_provider_update_revision_transitions")}
    return dict(**counts, cadence=cadence,
                observation_grid_minutes=expected_observation_minutes,
                observation_grid_aligned_timestamps=aligned,
                provider_updates_linked_to_multiple_observation_times=sum(len(v)>1 for v in update_observation_pairs.values()),
                provider_delay_rows=describe(first_delay_values),
                provider_delay_groups=describe([median(values) for values in delays.values()]),
                first_observation_age_rows=describe(first_age_values),
                cutoff_sensitivity={str(limit): {
                    field: interval_distribution(values, limit)["typical_intervals"]
                    for field, values in times.items()} for limit in (60, 120, 180)},
                provider_delay_interpretation=("unavailable: provider timestamp missing" if not delays else
                    "descriptive returned-record metadata offset; publication/version semantics not independently verified"))


def save_figure(fig, name):
    fig.savefig(HERE / "figures" / f"{name}.png", dpi=300, facecolor="white")
    fig.savefig(HERE / "figures" / f"{name}.pdf", facecolor="white",
                metadata={"Creator": "OutdoorWise data freshness analysis",
                          "CreationDate": None, "ModDate": None})
    plt.close(fig)


def select_figure_samples(samples):
    """Apply only the requested view filters; never reclassify or trim ages."""
    selected = []
    for sample in samples:
        if sample["collection_state"] != "active":
            continue
        fetched = datetime.fromisoformat(sample["fetched_at"])
        if fetched.tzinfo is None:
            raise ValueError("First-acquisition groups must have aware collection timestamps")
        if FIGURE_START <= fetched.astimezone(SGT) < FIGURE_END_EXCLUSIVE:
            selected.append(sample)
    return selected


def figure_display(sessions):
    display, summary = {}, []
    for source, session in sessions.items():
        samples = select_figure_samples(session["samples"])
        if not samples:
            raise ValueError(f"No active acquisitions in the requested Figure 1 window for {source}")
        display[source] = samples
        mid, mean, p90, maximum = statistics([
            (sample["fetched_at"], float(sample["observation_age_minutes"])) for sample in samples])
        summary.append(dict(source=source, collection_state="active",
                            window_start_inclusive=FIGURE_START.isoformat(),
                            window_end_exclusive=FIGURE_END_EXCLUSIVE.isoformat(),
                            displayed_fetch_timestamp_groups=len(samples),
                            valid_first_collection_records=sum(int(s["record_count"]) for s in samples),
                            first_displayed_collection_at=min(s["fetched_at"] for s in samples),
                            last_displayed_collection_at=max(s["fetched_at"] for s in samples),
                            median_age_minutes=mid, mean_age_minutes=mean,
                            p90_age_minutes=p90, maximum_age_minutes=maximum))
    return display, summary


def make_primary_figure(display):
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(7.16, 6.6), layout="constrained")
    fig.suptitle("Environmental Data Freshness During Active Collection", fontsize=11)
    for i, ((source, samples), ax) in enumerate(zip(display.items(), axes)):
        ages = [float(sample["observation_age_minutes"]) for sample in samples]
        ax.scatter([datetime.fromisoformat(s["fetched_at"]).astimezone(SGT) for s in samples],
                   ages, s=8, color=SOURCE_COLORS[source], alpha=0.65,
                   linewidths=0, rasterized=False, clip_on=False)
        ticks = MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]).tick_values(0, max(ages)*1.07)
        ax.set_ylim(0, ticks[-1])
        ax.set_yticks(ticks)
        ax.grid(axis="y", color="0.88", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.set_title(f"({chr(97+i)}) {source} — {PANEL_OBSERVATIONS[source]} (n = {len(samples):,})",
                     loc="left", fontsize=9, pad=5)
    axes[-1].set_xlim(FIGURE_START, FIGURE_END_EXCLUSIVE-timedelta(seconds=1))
    axes[-1].xaxis.set_major_locator(mdates.DayLocator(bymonthday=[8, 10, 12, 14, 16], tz=SGT))
    axes[-1].xaxis.set_major_formatter(FuncFormatter(
        lambda value, _position: f"Oct {mdates.num2date(value, tz=SGT).day}"))
    axes[-1].set_xlabel("Collection date (Oct 2026, SGT)")
    fig.supylabel("Observation age at first acquisition (minutes)", fontsize=10)
    return fig


def figures(summaries, display):
    plt.rcParams.update({"font.family": "serif", "font.serif": ["DejaVu Serif"],
                         "font.size": 9, "axes.labelsize": 9, "xtick.labelsize": 8,
                         "ytick.labelsize": 8, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.linewidth": 0.6,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    save_figure(make_primary_figure(display), "figure_1_observation_age_over_collection_time")

    fig, ax = plt.subplots(figsize=(7.16, 3.5), layout="constrained")
    ax.set_title("Revision-history evaluation: first collection and latest retained fetch", fontsize=10)
    positions = list(range(len(summaries)))
    width = 0.35
    a = [s[FIELDS[3]] for s in summaries]
    b = [s[FIELDS[7]] for s in summaries]
    bars_a = ax.bar([x-width/2 for x in positions], a, width,
                    label="Revision-1 first collection", color="#0072B2")
    bars_b = ax.bar([x+width/2 for x in positions], b, width,
                    label="Latest retained fetch (current tables)", color="#E69F00",
                    hatch="//", edgecolor="0.3", linewidth=0.4)
    for bars in (bars_a, bars_b):
        ax.bar_label(bars, labels=[f"{bar.get_height():.2f}" for bar in bars], padding=3, fontsize=8)
    ax.set_xticks(positions, list(SOURCES))
    ax.set_ylabel("Median of fetch-group median ages (minutes)")
    ax.set_ylim(0, max(a+b)*1.28)
    ax.grid(axis="y", color="0.88", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    save_figure(fig, "figure_2_first_collection_vs_latest_retained_fetch")


def write_csv(path, rows, fields=None):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: f"{value:.9f}" if isinstance(value, float) else value
                             for key, value in row.items()})


def render_report(sessions, summaries, display_summary):
    """Generate the main report from measured outputs, excluding supplementary Figure 2."""
    active_rows = []
    operation_rows = []
    display_rows = []
    for row in display_summary:
        display_rows.append(
            f"| {row['source']} | {row['displayed_fetch_timestamp_groups']:,} | "
            f"{row['median_age_minutes']:.2f} | {row['p90_age_minutes']:.2f} | {row['maximum_age_minutes']:.2f} |")
    for summary in summaries:
        source = summary["source"]
        active_rows.append(
            f"| {source} | {OFFICIAL[source][0]} | {OFFICIAL[source][1]} | "
            f"{summary['active_first_fetch_groups']:,} | {summary['median_observation_age_minutes']:.2f} | "
            f"{summary['active_median_age_minutes']:.2f} | {summary['active_p90_age_minutes']:.2f} |")
        operation = sessions[source]["operational"]
        operation_rows.append(
            f"| {source} | {operation['official_observation_cadence_minutes']} | "
            f"{operation['qualifying_active_successful_runs']:,} | {operation['runs_demonstrably_over_60_minutes']} | "
            f"{operation['maximum_demonstrated_age_lower_bound_minutes']:.2f} |")
    rain = sessions["Rainfall"]
    worst = max(rain["run_rows"], key=lambda row: row["returned_age_lower_bound_minutes"]
                if row["returned_age_lower_bound_minutes"] is not None else -math.inf)
    peak = max(rain["samples"], key=lambda sample: sample["observation_age_minutes"])
    total_groups = sum(len(session["samples"]) for session in sessions.values())
    total_records = sum(session["verification"]["matched_first_records"] for session in sessions.values())
    text = f"""# Data Freshness Evaluation — report-ready results and discussion

## A. Experimental Setup and Collection-Session Classification

We evaluated existing local environmental observations and ingestion logs from
October 2026 without making new provider requests. Source-specific observation
cadence, dataset refresh and aggregation were distinguished: rainfall station
updates occur every five minutes; WBGT is a 15-minute average updated every
15 minutes; PM2.5 is a one-hour concentration reported hourly; and PSI is a
rolling 24-hour index reported hourly. The PM2.5 and PSI datasets advertise
15-minute refreshes, which do not imply 15-minute observation labels. Official
citations and timestamp definitions are provided in the [methodology](README.md).

Observation age was calculated as fetch time minus observation time, interpreting
CSV timestamps in Singapore local time. Revision-1 records identify first recorded
acquisition. We linked all **{total_groups:,} first-fetch groups ({total_records:,} records)**
to unique successful same-source run intervals and reconciled their record counts
with insertion counters. Each fetch-timestamp group contributes its median age,
avoiding automatic weighting by station count.

The configured polling interval I is 5 minutes for rainfall and 15 minutes for
WBGT, PM2.5 and PSI. A run is log-supported active from the third consecutive
success when gaps from the previous completion to the next start are at most
2I + 0.5 minutes. A gap above 4I + 0.5 minutes starts a new log segment; its first
successful acquisition is post-gap if it passes the duration screen. Failed runs interrupt success chains.
Initial observations, warm-up, irregular polling and runs exceeding the 151.5-second
duration screen are classified as other/uncertain. These configuration-based
screening rules do not prove continuous laptop wakefulness or identify why a gap
occurred. Figure 1 applies only a display selection to the existing classification:
active first acquisitions collected from October 8 through 17, 2026, inclusive
(Asia/Singapore). No classification rules or original records are changed. The
full-period results, post-gap and uncertain acquisitions remain available.

## B. Observation Freshness During Active Collection

Table 1 reports unchanged **full-period** fetch-group statistics. The source-specific ages characterize our
pipeline's recorded first-acquisition timing; they are not comparable API speed
scores. Median/mode observation spacing in the retained history was 5, 15, 60 and
60 minutes for rainfall, WBGT, PM2.5 and PSI respectively.

| Source | Dataset refresh (min) | Observation cadence (min) | Active first-fetch groups | All-sample median age (min) | Active median age (min) | Active P90 age (min) |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(active_rows)}

Figure 1 displays only the October 8–17 active subset. Its displayed counts and
statistics are recalculated after both filters and stored separately in
`figure_1_display_summary.csv`; Table 1 and operational results retain their
original full-period scope.

| Source | Displayed first-fetch groups | Displayed median age (min) | Displayed P90 age (min) | Displayed maximum age (min) |
|---|---:|---:|---:|---:|
{chr(10).join(display_rows)}

The **{peak['observation_age_minutes']:.2f}-minute rainfall outlier** was observed at
{peak['minimum_observed_at']} and first fetched at {peak['fetched_at']}; it is
classified as post-gap and excluded from Figure 1. It remains in the unmodified
full-period acquisition records and statistics. Removing post-gap and uncertain samples
particularly reduces the air-quality age tails. This is conditioning on collection
state, not an improvement attributable to the collector. Varying the regular-gap
tolerance from 1.5I + 0.5 to 3I + 0.5 minutes yields active median ranges of
9.08 minutes for rainfall, 16.83–16.88 for WBGT, 9.19–9.20 for PM2.5 and
9.48–9.50 for PSI.

**Figure 1 caption.** Environmental observation age during log-supported active
collection from October 8 to 17, 2026 (Singapore time). Each point represents the
median observation age within a first-acquisition fetch-timestamp group. Only
acquisitions associated with regular successful polling sequences are included.
Repeated retrievals of unchanged observations are excluded. Rainfall and WBGT
observation timestamps typically advance every 5 and 15 minutes, respectively,
whereas PM2.5 and PSI observation timestamps advance hourly. These observation
intervals are distinct from the official dataset refresh schedules. Panel y-axis
ranges differ; all active acquisitions within the selected dates are retained.

This display selection examines normal active operation; it is not evidence that
excluded acquisitions never occurred. Genuine temporal gaps remain empty, with
no interpolation, smoothing or connected scatter points.

## C. Stale Observations Despite Successful Polling

First-acquisition selection omits successful polls that return existing records.
We therefore separately evaluated all qualifying active successful runs with
nonempty responses. These denominators include unchanged polls and are distinct
from Table 1's first-fetch group counts.

For each run r, let M_r be the newest observation timestamp introduced in the
complete revision-1 history up to and including that run. Reconciliation against
every successful run's insertion counter checks completeness of introductions.
Any observation returned in that run has a timestamp no later than M_r. Since
fetching occurs after the logged run start s_r, its age is at least s_r - M_r.
Including introductions within the current run makes this bound conservative.
The calculation bounds returned ages; it does not reconstruct discarded payloads.

| Source | Official observation cadence (min) | Qualifying active successful runs | Runs demonstrably >60 min old | Maximum demonstrated age lower bound (min) |
|---|---:|---:|---:|---:|
{chr(10).join(operation_rows)}

The 60-minute cutoff is an analysis diagnostic, **not an official API SLA**. Counts
are minimum demonstrated cases under the conservative bound, not complete stale
response prevalence. Zero WBGT cases do not prove that every WBGT response was
recent. The maximum column covers all qualifying runs, including those below
60 minutes. Consecutive old responses are correlated and are not counted as
independent outage events.

For example, the rainfall run at **{worst['started_at']} SGT** logged
{worst['received_records']} unchanged records, only {worst['quiet_gap_minutes']:.2f} minutes after
the preceding success. Its newest known observation was
{worst['newest_known_observed_at']}, giving an age lower bound of
**{worst['returned_age_lower_bound_minutes']:.2f} minutes** (ingestion-log line {worst['log_line']}).
Thus, successful HTTP retrieval alone is insufficient to establish the recency
of the environmental measurements used by our pipeline.

## D. Limitations

Collection was intermittent on a local MacBook. Log-derived states cannot identify
sleep, shutdown or continuous wakefulness, and do not establish intended uptime.
The 379-minute post-gap outlier must not be attributed to government API failure.
The first-acquisition statistics omit unchanged repeat responses; the operational
bounds address some of that missing evidence but do not recover exact payloads or
full response-age distributions. Their validity relies on the retained history,
counter semantics and consistent local timestamps; historical raw responses are
not available for independent verification of every request.
Figure 1 is a date-restricted active first-acquisition view, not a complete history
of every successful API response. Operational freshness is evaluated separately
from the full ingestion logs in Section C.

Source reporting schedules, aggregation periods, polling phase and metadata updates
also differ. Nominal cadence is not a maximum-age guarantee. Provider update
timestamps are not verified exact publication times, so their fetch offsets are
descriptive only. No HTTP latency, government API availability, causal performance
improvement or improvement in source freshness is claimed. The first-versus-latest
retention comparison is preserved as supplementary reproducibility evidence and
excluded from the main evaluation: its difference is largely explained by
metadata-only revisions and repeated retrieval of unchanged hourly observations.
"""
    (HERE / "RESULTS.md").write_text(text, encoding="utf-8")


def main():
    paths = sorted({ROOT / "data/runtime" / f"{group}_{suffix}.csv"
                    for group, _, _ in SOURCES.values()
                    for suffix in ("observation_versions", "observations")})
    before = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    pinned = json.loads((Path(__file__).resolve().parent / "audited_input_sha256.json").read_text())
    if before != pinned:
        raise ValueError("Inputs differ from the audited source CSV hashes; review before revising the baseline")
    config_path = ROOT / "config/environment.toml"
    config_hash = digest(config_path)
    log_path = ROOT / "data/runtime/ingestion_runs.csv"
    supporting_hashes = {"config/environment.toml": config_hash,
                         "data/runtime/ingestion_runs.csv": digest(log_path)}
    session_pins = json.loads((Path(__file__).resolve().parent / "audited_session_inputs_sha256.json").read_text())
    if supporting_hashes != session_pins:
        raise ValueError("Session inputs differ from the completed inactivity audit baseline")
    with config_path.open("rb") as handle:
        configuration = tomllib.load(handle)
    logs = read_runs(log_path)
    collection = configuration["collection"]
    duration_limit = ((collection["max_retries"]+1)*collection["timeout_seconds"] +
                      collection["max_retries"]*collection["max_retry_delay_seconds"] +
                      collection["request_spacing_seconds"] + 30)/60
    first, summaries, verification, sessions = {}, [], {}, {}
    interval_rows = []
    for source, (group, metric, provider) in SOURCES.items():
        points, initial = read_groups(ROOT / "data/runtime" / f"{group}_observation_versions.csv", metric, provider, True)
        current, latest = read_groups(ROOT / "data/runtime" / f"{group}_observations.csv", metric, provider, False)
        values = (initial["valid_records"], len(points), *statistics(points), statistics(current)[0])
        expected = AUDIT[source]
        if values[:2] != expected[:2] or any(abs(x-y) > 0.005001 for x,y in zip(values[2:], expected[2:])):
            raise ValueError(f"Data no longer matches audited results for {source}: {values}")
        first[source] = points
        summary = dict(zip(FIELDS, (source, *values)))
        history = history_diagnostics(ROOT / "data/runtime" / f"{group}_observation_versions.csv",
                                      metric, provider, OFFICIAL[source][1])
        observed = history["cadence"]["observed_at"]
        update = history["cadence"]["source_updated_at"]
        delay = history["provider_delay_groups"]
        for field, result in history["cadence"].items():
            for seconds, count in result["histogram_seconds"].items():
                interval_rows.append(dict(source=source, timestamp_field=field, interval_seconds=seconds,
                                          interval_minutes=seconds/60, count=count,
                                          included_in_typical_cadence=seconds <= CADENCE_GAP_LIMIT_MINUTES*60))
        summary.update(dict(zip(CADENCE_FIELDS, (
            OFFICIAL[source][0], OFFICIAL[source][2], configuration["sources"][provider]["interval_seconds"]/60,
            observed["typical_intervals"]["median"], ";".join(f"{v:.9f}" for v in observed["typical_intervals"]["mode"]),
            observed["typical_intervals"]["p90"], observed["typical_intervals"]["n"], observed["excluded_intervals"],
            update["typical_intervals"]["median"], ";".join(f"{v:.9f}" for v in update["typical_intervals"]["mode"]),
            update["typical_intervals"]["p90"], history["provider_delay_rows"]["n"], delay["n"],
            delay["median"], delay["p90"], delay["maximum"], history["missing_provider_update_first_records"],
            history["negative_provider_delay_first_records"], history["provider_delay_interpretation"]))))
        # Annotation values are checked against empirical results, not just copied from standards.
        if (observed["typical_intervals"]["median"] != OFFICIAL[source][1] or
                observed["typical_intervals"]["mode"] != [OFFICIAL[source][1]]):
            raise ValueError(f"Review cadence annotations for {source}")
        session = evaluate_source(ROOT / "data/runtime" / f"{group}_observation_versions.csv",
                                  logs, source, provider, metric,
                                  configuration["sources"][provider]["interval_seconds"]/60,
                                  duration_limit, OFFICIAL[source][1], OFFICIAL[source][0])
        sessions[source] = session
        states = {row["selection"]: row for row in session["summary"]}
        active, post, other = (states[key] for key in ("active", "post_gap_first", "other_uncertain"))
        operation = session["operational"]
        checkpoint = (active["fetch_timestamp_groups"], round(active["median_age_minutes"], 2),
                      operation["qualifying_active_successful_runs"], operation["runs_demonstrably_over_60_minutes"],
                      post["fetch_timestamp_groups"], other["fetch_timestamp_groups"])
        if checkpoint != SESSION_AUDIT[source]:
            raise ValueError(f"Session results disagree with inactivity audit for {source}: {checkpoint}")
        summary.update(dict(zip(SESSION_FIELDS, (
            active["fetch_timestamp_groups"], active["median_age_minutes"], active["mean_age_minutes"],
            active["p90_age_minutes"], active["maximum_age_minutes"], post["fetch_timestamp_groups"],
            other["fetch_timestamp_groups"], operation["qualifying_active_successful_runs"],
            operation["runs_demonstrably_over_60_minutes"], operation["maximum_demonstrated_age_lower_bound_minutes"]))))
        summaries.append(summary)
        verification[source] = {"first_collection": initial, "latest_retained_fetch": latest,
                                "matches_previous_audit_to_two_decimals": True,
                                "history_diagnostics": history,
                                "session_audit": session["verification"],
                                "operational_freshness": operation,
                                "matches_inactivity_audit": True}
    if before != {str(p.relative_to(ROOT)): digest(p) for p in paths}:
        raise RuntimeError("Inputs changed while being read; do not use this run")
    (HERE / "figures").mkdir(exist_ok=True)
    display, display_summary = figure_display(sessions)
    figures(summaries, display)
    if before != {str(p.relative_to(ROOT)): digest(p) for p in paths}:
        raise RuntimeError("Inputs changed during figure generation; do not use this run")
    write_csv(HERE / "summary.csv", summaries, FIELDS+CADENCE_FIELDS+SESSION_FIELDS)
    for filename, key in (("session_summary.csv", "summary"),
                          ("first_acquisition_samples.csv", "samples"),
                          ("session_run_audit.csv", "run_rows"),
                          ("session_sensitivity.csv", "sensitivity")):
        write_csv(HERE / filename, [row for session in sessions.values() for row in session[key]])
    write_csv(HERE / "operational_freshness.csv", [session["operational"] for session in sessions.values()])
    write_csv(HERE / "figure_1_display_summary.csv", display_summary)
    write_csv(HERE / "figure_1_display_points.csv", [sample for samples in display.values() for sample in samples])
    render_report(sessions, summaries, display_summary)
    with (HERE / "cadence_interval_distribution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(interval_rows[0]))
        writer.writeheader()
        writer.writerows(interval_rows)
    if any(digest(ROOT / path) != expected for path, expected in supporting_hashes.items()):
        raise RuntimeError("Session inputs changed during analysis")
    manifest = {"input_sha256": before, "input_hashes_unchanged": True,
                "supporting_input_sha256": supporting_hashes,
                "official_documentation_review_date": "2026-10-29",
                "cadence_interval_exclusion": "Exclude intervals >120 minutes for typical cadence only; retain all ages and plot points",
                "operational_bound_assumptions": [
                    "All first-acquisition groups uniquely associate with source run intervals",
                    "First introductions reconcile with every successful run's insertion counters",
                    "Observation keys include observed_at and revision history is retained",
                    "Run start/finish and CSV times use consistent Singapore-local clock semantics",
                    "Bounds and run counts do not identify independent outages or API SLA failures"],
                "python_version": platform.python_version(), "matplotlib_version": matplotlib.__version__,
                "p90_method": "linear interpolation at (n-1)*0.9",
                "statistics_unit": "one median observation age per source/fetched_at group",
                "sources": verification}
    (HERE / "verification.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))
    print("Verified: original and inactivity audit agreement, unique temporal joins, insertion counters, unchanged input hashes.")


if __name__ == "__main__":
    main()
