"""Verify the display selection without changing collection-state methodology."""
from copy import deepcopy

import matplotlib.pyplot as plt
import pytest

from analysis.data_freshness.analyze import (
    SOURCES, figure_display, make_primary_figure, select_figure_samples,
)


def sample(time, state="active", age=10):
    return dict(fetched_at=time, collection_state=state,
                observation_age_minutes=age, record_count=1)


def test_display_filters_state_and_singapore_dates_without_mutating_records():
    rows = [sample("2026-10-07T23:59:59+08:00"),
            sample("2026-10-08T00:00:00+08:00"),
            sample("2026-10-17T23:59:59.999999+08:00"),
            sample("2026-10-18T00:00:00+08:00"),
            sample("2026-10-27T12:00:00+08:00"),
            sample("2026-10-10T12:00:00+08:00", "post_gap_first"),
            sample("2026-10-10T12:00:00+08:00", "other_uncertain"),
            sample("2026-10-07T16:00:00+00:00"),  # Oct 8 midnight SGT.
            sample("2026-10-17T16:00:00+00:00")]
    original = deepcopy(rows)
    assert select_figure_samples(rows) == [rows[1], rows[2], rows[7]]
    assert rows == original


def test_selection_preserves_active_outliers_and_rejects_naive_times():
    outlier = sample("2026-10-12T12:00:00+08:00", age=400)
    assert select_figure_samples([outlier]) == [outlier]
    with pytest.raises(ValueError, match="aware"):
        select_figure_samples([sample("2026-10-12T12:00:00")])


def test_plot_contains_every_selected_point_without_connections_or_clipping():
    sessions = {source: {"samples": [
        sample("2026-10-08T00:00:00+08:00", age=0),
        sample("2026-10-17T23:00:00+08:00", age=17+i),
        sample("2026-10-10T12:00:00+08:00", "post_gap_first", 400),
    ]} for i, source in enumerate(SOURCES)}
    display, summary = figure_display(sessions)
    assert [row["displayed_fetch_timestamp_groups"] for row in summary] == [2]*4
    fig = make_primary_figure(display)
    try:
        assert len(fig.axes) == 4 and not fig.legends
        for ax, samples in zip(fig.axes, display.values()):
            assert len(ax.collections) == 1
            points = ax.collections[0].get_offsets()
            assert len(points) == len(samples)
            assert list(points[:, 1]) == [s["observation_age_minutes"] for s in samples]
            assert ax.get_ylim()[0] <= min(points[:, 1]) <= max(points[:, 1]) < ax.get_ylim()[1]
            assert not ax.lines and not ax.texts and ax.get_legend() is None
    finally:
        plt.close(fig)
