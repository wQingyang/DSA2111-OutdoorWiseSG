"""Validate run joins, inactivity boundaries, and conservative freshness bounds."""
import csv
from datetime import timedelta

import pytest

from analysis.data_freshness.session_audit import (
    classify_runs, evaluate_source, local_time, unique_successful_run,
)

START = local_time("2026-10-05T00:00:00")


def run(at, *, duration=0, status="success", inserted=0, received=1):
    start = START + timedelta(minutes=at)
    end = start + timedelta(minutes=duration)
    return dict(source="nea_rainfall", source_kind="live", run_id=f"run-{at}",
                started_at=start.strftime("%Y-%m-%dT%H:%M:%S"),
                finished_at=end.strftime("%Y-%m-%dT%H:%M:%S"), status=status,
                inserted_records=str(inserted), received_records=str(received),
                revised_records="0", unchanged_records=str(received-inserted),
                _start=start, _end=end, _duration=duration, _log_line=2)


def test_active_requires_three_successes_and_failure_interrupts_chain():
    rows = [run(0), run(5), run(10), run(15, status="failed"), run(20), run(25), run(30)]
    states = [row["_state"] for row in classify_runs(rows, 5, 2.525)]
    assert states == ["initial_first", "other_irregular_or_warmup", "active", "failed",
                      "other_irregular_or_warmup", "other_irregular_or_warmup", "active"]


def test_extended_gap_is_strict_and_long_duration_is_uncertain():
    rows = classify_runs([run(0), run(20.5), run(41.02), run(46.02, duration=3)], 5, 2.525)
    assert rows[1]["_state"] == "other_irregular_or_warmup"
    assert rows[2]["_state"] == "post_gap_first"
    assert rows[3]["_state"] == "long_running"


def test_temporal_join_rejects_missing_and_ambiguous_matches():
    with pytest.raises(ValueError, match="0 successful-run"):
        unique_successful_run(START+timedelta(minutes=1), [run(0)])
    with pytest.raises(ValueError, match="2 successful-run"):
        unique_successful_run(START+timedelta(minutes=5), [run(0, duration=5), run(5)])


def history_file(tmp_path, entries):
    path = tmp_path / "history.csv"
    fields = ["source", "source_kind", "metric", "revision", "observed_at", "fetched_at", "source_updated_at"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for observed, fetched in entries:
            writer.writerow(dict(source="nea_rainfall", source_kind="live", metric="rainfall", revision="1",
                                 observed_at=(START+timedelta(minutes=observed)).strftime("%Y-%m-%dT%H:%M:%S"),
                                 fetched_at=(START+timedelta(minutes=fetched)).strftime("%Y-%m-%dT%H:%M:%S"),
                                 source_updated_at=""))
    return path


def test_operational_denominator_includes_unchanged_runs_without_future_leakage(tmp_path):
    # A newly introduced observation at minute 70 cannot freshen the bound at 65.
    path = history_file(tmp_path, [(0, 0), (69, 70)])
    runs = [run(at, inserted=int(at in {0, 70})) for at in range(0, 71, 5)]
    result = evaluate_source(path, runs, "Rainfall", "nea_rainfall", "rainfall", 5, 2.525, 5, 5)
    operational = result["operational"]
    assert operational["qualifying_active_successful_runs"] == 13
    assert operational["runs_demonstrably_over_60_minutes"] == 1
    assert operational["maximum_demonstrated_age_lower_bound_minutes"] == 65
    at_60 = next(row for row in result["run_rows"] if row["run_id"] == "run-60")
    assert not at_60["demonstrated_over_60_minutes"]  # Strictly >60, not >=60.
    at_70 = next(row for row in result["run_rows"] if row["run_id"] == "run-70")
    assert at_70["returned_age_lower_bound_minutes"] == 1
    assert len(result["samples"]) == 2  # Distinct from the 13-run denominator.


def test_bound_uses_run_start_instead_of_response_finish(tmp_path):
    path = history_file(tmp_path, [(0, 0)])
    result = evaluate_source(path, [run(0, inserted=1), run(30), run(60, duration=2)],
                             "WBGT-test", "nea_rainfall", "rainfall", 15, 2.525, 15, 15)
    active = result["run_rows"][-1]
    assert active["qualifying_active_success"]
    assert active["returned_age_lower_bound_minutes"] == 60
    assert not active["demonstrated_over_60_minutes"]


def test_incomplete_introduction_history_prevents_operational_inference(tmp_path):
    path = history_file(tmp_path, [(0, 0)])
    with pytest.raises(ValueError, match="counts disagree"):
        evaluate_source(path, [run(0, inserted=0)], "Rainfall", "nea_rainfall", "rainfall", 5, 2.525, 5, 5)
