"""Offline session classification and conservative bounds from ingestion counters.

No application imports or repository initialization. A run interval associates
retained first acquisitions with logs; it does not reconstruct discarded payloads.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime
import math
import re
from statistics import fmean, median
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")
SCHEDULING_GRACE_MINUTES = 0.5
OLD_OBSERVATION_DIAGNOSTIC_MINUTES = 60
METRICS_PER_RESPONSE_ROW = {"nea_rainfall": 1, "nea_wbgt": 2, "nea_pm25": 1, "nea_psi": 2}


def local_time(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
        raise ValueError(f"Expected Singapore-local CSV v3 timestamp: {value!r}")
    return datetime.fromisoformat(value).replace(tzinfo=SGT)


def minutes(later, earlier):
    return (later-earlier).total_seconds()/60


def summarize(values):
    values = sorted(values)
    if not values:
        return dict(n=0, median=None, mean=None, p90=None, maximum=None)
    position = (len(values)-1)*0.9
    left = math.floor(position)
    p90 = values[left] + (values[min(left+1, len(values)-1)]-values[left])*(position-left)
    return dict(n=len(values), median=median(values), mean=fmean(values), p90=p90, maximum=max(values))


def read_runs(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len({row["run_id"] for row in rows}) != len(rows):
        raise ValueError("Ingestion log has duplicate run IDs")
    for line, row in enumerate(rows, 2):
        row["_start"], row["_end"] = local_time(row["started_at"]), local_time(row["finished_at"])
        row["_duration"] = minutes(row["_end"], row["_start"])
        row["_log_line"] = line
        if row["_duration"] < 0:
            raise ValueError(f"Negative ingestion run duration at line {line}")
        if row["status"] == "success" and int(row["received_records"]) != sum(
                int(row[field]) for field in ("inserted_records", "revised_records", "unchanged_records")):
            raise ValueError(f"Acquisition counters do not reconcile at line {line}")
    return rows


def classify_runs(runs, polling_minutes, duration_limit_minutes,
                  regular_multiplier=2, extended_multiplier=4, required_successes=3):
    """Label third and subsequent timely successes; preserve uncertain states."""
    result = []
    previous = None
    seen_success = False
    session_successes = streak = session = 0
    extended = False
    for original in sorted(runs, key=lambda run: run["_start"]):
        run = original.copy()
        quiet = minutes(run["_start"], previous["_end"]) if previous else None
        if quiet is not None and quiet < 0:
            raise ValueError("Overlapping source run intervals cannot support this session audit")
        if previous is None or quiet > extended_multiplier*polling_minutes+SCHEDULING_GRACE_MINUTES:
            session += 1
            session_successes = 0
            extended = previous is not None
            streak = 0
        short = run["_duration"] <= duration_limit_minutes
        linked = (previous is not None and previous["status"] == "success" and
                  previous["_duration"] <= duration_limit_minutes and short and
                  quiet <= regular_multiplier*polling_minutes+SCHEDULING_GRACE_MINUTES)
        streak = (streak+1 if linked else 1) if run["status"] == "success" and short else 0
        state = "failed"
        if run["status"] == "success":
            if not short:
                state = "long_running"
            elif session_successes == 0 and extended:
                state = "post_gap_first"
            elif not seen_success:
                state = "initial_first"
            elif streak >= required_successes:
                state = "active"
            else:
                state = "other_irregular_or_warmup"
            session_successes += 1
            seen_success = True
        run.update(_state=state, _session=session, _quiet_gap=quiet, _streak=streak)
        result.append(run)
        previous = run
    return result


def unique_successful_run(fetched, successful_runs):
    candidates = [run for run in successful_runs if run["_start"] <= fetched <= run["_end"]]
    if len(candidates) != 1:
        raise ValueError(f"Fetch {fetched.isoformat()} has {len(candidates)} successful-run candidates")
    return candidates[0]


def display_state(state):
    return state if state in {"active", "post_gap_first"} else "other_uncertain"


def evaluate_source(history_path, logs, source_name, source, metric, polling_minutes,
                    duration_limit_minutes, official_observation_minutes, official_update_minutes):
    runs = classify_runs([row for row in logs if row["source"] == source and row["source_kind"] == "live"],
                         polling_minutes, duration_limit_minutes)
    successful = [run for run in runs if run["status"] == "success"]
    by_run = defaultdict(list)
    records_by_fetch = defaultdict(list)
    with history_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["source_kind"] == "live" and row["source"] == source and row["metric"] == metric and row["revision"] == "1":
                records_by_fetch[local_time(row["fetched_at"])].append(row)
    samples = []
    for fetched, rows in sorted(records_by_fetch.items()):
        run = unique_successful_run(fetched, successful)
        observed = [local_time(row["observed_at"]) for row in rows]
        offsets = [minutes(fetched, local_time(row["source_updated_at"]))
                   for row in rows if row["source_updated_at"]]
        sample = dict(source=source_name, fetched_at=fetched.isoformat(), run_id=run["run_id"],
                      run_log_line=run["_log_line"], run_state=run["_state"],
                      collection_state=display_state(run["_state"]), record_count=len(rows),
                      minimum_observed_at=min(observed).isoformat(), maximum_observed_at=max(observed).isoformat(),
                      observation_age_minutes=median(minutes(fetched, time) for time in observed),
                      provider_update_to_fetch_minutes=median(offsets) if offsets else None,
                      provider_update_records=len(offsets))
        samples.append(sample)
        by_run[run["run_id"]].append(sample)
    factor = METRICS_PER_RESPONSE_ROW[source]
    for run in successful:
        assigned = sum(sample["record_count"] for sample in by_run[run["run_id"]])
        if assigned*factor != int(run["inserted_records"]):
            raise ValueError(f"First-acquisition counts disagree with run {run['run_id']}")
    summary = []
    for state in ("all_recorded", "active", "post_gap_first", "other_uncertain"):
        selected = samples if state == "all_recorded" else [s for s in samples if s["collection_state"] == state]
        ages = summarize([s["observation_age_minutes"] for s in selected])
        offsets = summarize([s["provider_update_to_fetch_minutes"] for s in selected
                             if s["provider_update_to_fetch_minutes"] is not None])
        summary.append(dict(source=source_name, selection=state,
                            valid_first_collection_records=sum(s["record_count"] for s in selected),
                            fetch_timestamp_groups=ages["n"], median_age_minutes=ages["median"],
                            mean_age_minutes=ages["mean"], p90_age_minutes=ages["p90"], maximum_age_minutes=ages["maximum"],
                            provider_offset_groups=offsets["n"], provider_offset_median_minutes=offsets["median"],
                            provider_offset_p90_minutes=offsets["p90"], provider_offset_maximum_minutes=offsets["maximum"]))

    # Completeness of first introductions was checked against *every* successful
    # run's insertion counter. Include introductions in this run when bounding
    # returned timestamps; doing so can only make the lower bound smaller.
    newest = None
    run_rows = []
    for run in runs:
        introductions = by_run[run["run_id"]]
        for sample in introductions:
            observed = datetime.fromisoformat(sample["maximum_observed_at"])
            newest = max(newest, observed) if newest else observed
        eligible = (run["_state"] == "active" and int(run["received_records"]) > 0 and newest is not None)
        bound = minutes(run["_start"], newest) if eligible else None
        run_rows.append(dict(source=source_name, run_id=run["run_id"], log_line=run["_log_line"],
                             started_at=run["started_at"], finished_at=run["finished_at"], status=run["status"],
                             run_state=run["_state"], session_index=run["_session"],
                             consecutive_successes=run["_streak"], quiet_gap_minutes=run["_quiet_gap"],
                             duration_minutes=run["_duration"],
                             received_records=int(run["received_records"]), inserted_records=int(run["inserted_records"]),
                             revised_records=int(run["revised_records"]), unchanged_records=int(run["unchanged_records"]),
                             associated_first_records=sum(s["record_count"] for s in introductions),
                             qualifying_active_success=eligible,
                             newest_known_observed_at=newest.isoformat() if newest else None,
                             returned_age_lower_bound_minutes=bound,
                             demonstrated_over_60_minutes=eligible and bound > OLD_OBSERVATION_DIAGNOSTIC_MINUTES,
                             evidence_kind="inferred bound from complete acquisition history and counters" if eligible else "not evaluated"))
    eligible = [row for row in run_rows if row["qualifying_active_success"]]
    old = [row for row in eligible if row["demonstrated_over_60_minutes"]]
    operation = dict(source=source_name, qualifying_active_successful_runs=len(eligible),
                     runs_demonstrably_over_60_minutes=len(old),
                     maximum_demonstrated_age_lower_bound_minutes=max(
                         (row["returned_age_lower_bound_minutes"] for row in eligible), default=None),
                     official_observation_cadence_minutes=official_observation_minutes,
                     official_dataset_update_minutes=official_update_minutes,
                     diagnostic_threshold_minutes=OLD_OBSERVATION_DIAGNOSTIC_MINUTES,
                     evidence_kind="inferred lower bounds; not exact retained response payloads",
                     interpretation="conditional run counts, not independent outage events or an API SLA")
    sensitivity = []
    for multiplier in (1.5, 2, 3):
        classified = classify_runs(runs, polling_minutes, duration_limit_minutes, regular_multiplier=multiplier)
        states = {run["run_id"]: run["_state"] for run in classified}
        selected = [s for s in samples if states[s["run_id"]] == "active"]
        ages = summarize([s["observation_age_minutes"] for s in selected])
        sensitivity.append(dict(source=source_name, regular_gap_multiplier=multiplier,
                                regular_gap_limit_minutes=multiplier*polling_minutes+SCHEDULING_GRACE_MINUTES,
                                active_first_fetch_groups=ages["n"], median_age_minutes=ages["median"],
                                p90_age_minutes=ages["p90"], maximum_age_minutes=ages["maximum"]))
    verification = dict(unique_interval_matches=len(samples), matched_first_records=sum(s["record_count"] for s in samples),
                        ambiguous_or_unmatched_first_fetch_groups=0, insertion_counter_mismatches=0,
                        polling_minutes=polling_minutes, regular_gap_limit_minutes=2*polling_minutes+SCHEDULING_GRACE_MINUTES,
                        extended_gap_limit_minutes=4*polling_minutes+SCHEDULING_GRACE_MINUTES,
                        maximum_run_duration_minutes=duration_limit_minutes,
                        run_state_counts=dict(Counter(run["_state"] for run in runs)),
                        session_segments=max((run["_session"] for run in runs), default=0))
    return dict(samples=samples, summary=summary, run_rows=run_rows, operational=operation,
                sensitivity=sensitivity, verification=verification)
