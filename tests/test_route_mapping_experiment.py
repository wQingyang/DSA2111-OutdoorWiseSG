from datetime import datetime, timedelta, timezone

import pytest

from outdoorwise.config import ROOT, load_environment_config
from outdoorwise.contracts.environment import EnvironmentObservation, Location, METRIC_SPECS
from outdoorwise.contracts.models import LineString, Route
from outdoorwise.contracts.geo import distance_km
from experiments.station_route_matching.scripts.compare_route_mapping import compare_snapshot, sample_route_points

AS_OF = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)
CONFIG = load_environment_config(ROOT / "config/environment.toml")


class SnapshotRepository:
    def __init__(self, coordinates, locations=(), observations=()):
        self.route = Route(route_id="test_route", name="Test route", kind="point_to_point",
                           distance_km=1, status="test", attribution="test",
                           geometry=LineString(coordinates=coordinates))
        self.locations = list(locations)
        self.observations = list(observations)

    def load_routes(self):
        return [self.route]

    def environment_snapshot(self, source_kind, as_of):
        return self.locations, self.observations, []


def station(location_id, lon, *, source="nea_rainfall"):
    return Location(source=source, location_id=location_id, name=location_id, location_type="station",
                    lon=lon, lat=1.3, source_kind="demo", metadata_updated_at=AS_OF)


def observation(location_id, value, *, observed_at=AS_OF, metric="rainfall", source="nea_rainfall"):
    unit, window, _ = METRIC_SPECS[metric]
    return EnvironmentObservation(source=source, location_id=location_id, observed_at=observed_at,
        fetched_at=observed_at, first_fetched_at=observed_at, metric=metric, value=value,
        unit=unit, aggregation_window=window, source_kind="demo")


def rows_for(repository, *, config=CONFIG):
    samples, summaries = compare_snapshot(repository, config, "demo", AS_OF)
    selected = [row for row in samples if row["metric"] == "rainfall"]
    summary = next(row for row in summaries if row["metric"] == "rainfall" and row["method"] == "along_route_500m")
    return selected, summary


def test_nearest_matching_selects_closest_of_multiple_usable_stations():
    repo = SnapshotRepository([(103.8, 1.3), (103.81, 1.3)],
        [station("far", 103.82), station("near", 103.801)],
        [observation("far", 8), observation("near", 3)])
    samples, _ = rows_for(repo)
    start = next(row for row in samples if row["method"] == "nearest_start")
    assert start["matched_location_id"] == "near"
    assert start["value"] == 3


def test_along_route_reports_partial_coverage_under_distance_limit():
    constrained = CONFIG.model_copy(update={"matching": CONFIG.matching.model_copy(update={"station_max_distance_km": 0.7})})
    repo = SnapshotRepository([(103.8, 1.3), (103.82, 1.3)],
        [station("west", 103.8), station("east", 103.82)],
        [observation("west", 1), observation("east", 2)])
    _, summary = rows_for(repo, config=constrained)
    assert 0 < summary["matched_count"] < summary["sample_count"]
    assert 0 < summary["coverage_ratio"] < 1


def test_all_missing_observations_have_zero_coverage_and_blank_values():
    repo = SnapshotRepository([(103.8, 1.3), (103.81, 1.3)], [station("s", 103.8)], [])
    samples, summary = rows_for(repo)
    assert summary["matched_count"] == 0
    assert summary["coverage_ratio"] == 0
    assert summary["mean_numeric_value"] == ""
    assert all(row["match_status"] == "missing" and row["value"] == "" for row in samples if row["method"] == "along_route_500m")


def test_stale_station_is_retained_and_reported_separately():
    stale_at = AS_OF - timedelta(seconds=CONFIG.sources["nea_rainfall"].stale_after_seconds + 1)
    repo = SnapshotRepository([(103.8, 1.3), (103.81, 1.3)], [station("stale", 103.8)],
                              [observation("stale", 4, observed_at=stale_at)])
    samples, summary = rows_for(repo)
    along = [row for row in samples if row["method"] == "along_route_500m"]
    assert summary["stale_matched_count"] == len(along)
    assert summary["fresh_matched_count"] == 0
    assert all(row["freshness"] == "stale" for row in along)


def test_long_route_sampling_has_both_endpoints_and_unbounded_full_coverage():
    coords = [(103.8, 1.3), (103.9, 1.3), (104.0, 1.3), (104.1, 1.3)]
    points = sample_route_points(coords)
    length = sum(distance_km(type(points[0])(lon=a[0], lat=a[1]), type(points[0])(lon=b[0], lat=b[1]))
                 for a, b in zip(coords, coords[1:]))
    assert points[0].lon == coords[0][0] and points[0].lat == coords[0][1]
    assert points[-1].lon == coords[-1][0] and points[-1].lat == coords[-1][1]
    assert len(points) > 30
    assert len(points) >= int(length / 0.5)
    spacings = [distance_km(left, right) for left, right in zip(points, points[1:])]
    assert max(spacings) <= 0.51


def test_assessment_requires_timezone_aware_datetime():
    repo = SnapshotRepository([(103.8, 1.3), (103.81, 1.3)])
    with pytest.raises(ValueError, match="timezone"):
        compare_snapshot(repo, CONFIG, "demo", datetime(2026, 10, 24))
