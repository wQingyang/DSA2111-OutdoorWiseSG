"""Focused checks for cadence screening and interpretation of update metadata."""
import csv
from datetime import datetime, timedelta

import pytest

from analysis.data_freshness.analyze import (
    csv_time, describe, history_diagnostics, interval_distribution,
)


def test_csv_local_time_and_offset_free_contract():
    time = csv_time("2026-10-05T11:00:00")
    assert time.utcoffset() == timedelta(hours=8)
    with pytest.raises(ValueError):
        csv_time("2026-10-05T11:00:00Z")


def test_interval_screen_keeps_boundary_and_deduplicates_timestamps():
    start = csv_time("2026-10-05T11:00:00")
    values = [start + timedelta(minutes=offset) for offset in (0, 0, 60, 180, 360)]
    result = interval_distribution(values)
    assert result["unique_timestamps"] == 4
    assert result["typical_intervals"]["n"] == 2
    assert result["typical_intervals"]["median"] == 90
    assert result["typical_intervals"]["p90"] == 114
    assert result["excluded_intervals"] == 1
    assert result["histogram_seconds"] == {3600: 1, 7200: 1, 10800: 1}


def test_missing_distribution_is_unavailable_and_tied_modes_are_preserved():
    assert describe([])["median"] is None
    assert describe([5, 5, 10, 10])["mode"] == [5, 10]


def test_revision_offsets_use_same_row_update_and_only_first_revision(tmp_path):
    fields = ["source", "source_kind", "metric", "location_id", "observed_at", "fetched_at",
              "source_updated_at", "revision", "aggregation_window", "value", "category_value",
              "unit", "raw_value", "raw_unit"]
    common = dict(source="nea_pm25", source_kind="live", metric="pm25", location_id="north",
                  observed_at="2026-10-05T11:00:00", aggregation_window="PT1H", value="10",
                  category_value="", unit="ug/m3", raw_value="10", raw_unit="ug/m3")
    rows = [dict(common, revision="1", source_updated_at="2026-10-05T11:01:00",
                 fetched_at="2026-10-05T11:03:00"),
            dict(common, revision="2", source_updated_at="2026-10-05T11:16:00",
                 fetched_at="2026-10-05T11:20:00"),
            dict(common, location_id="south", revision="1", source_updated_at="",
                 fetched_at="2026-10-05T11:03:00")]
    path = tmp_path / "history.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = history_diagnostics(path, "pm25", "nea_pm25", 60)
    assert result["provider_delay_groups"]["median"] == 2
    assert result["provider_delay_rows"]["n"] == 1
    assert result["missing_provider_update_first_records"] == 1
    assert result["update_only_revision_transitions"] == 1
    assert result["cadence"]["source_updated_at"]["typical_intervals"]["median"] == 15
    # Negative provider offsets must be visible, never clipped to zero or silently removed.
    rows[0]["source_updated_at"] = "2026-10-05T11:04:00"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = history_diagnostics(path, "pm25", "nea_pm25", 60)
    assert result["negative_provider_delay_first_records"] == 1
    assert result["provider_delay_groups"]["median"] == -1
