"""Compare fixed-route station matching methods against one stored snapshot.

This is an offline experiment. It reads the CSV repository and never collects data.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outdoorwise.config import load_environment_config
from outdoorwise.contracts.core import Coordinate
from outdoorwise.contracts.environment import METRIC_SPECS
from outdoorwise.contracts.geo import distance_km
from outdoorwise.storage.repository import FileRepository

METHODS = ("nearest_start", "nearest_end", "along_route_500m")
REGIONAL_METRICS = {"pm25", "psi", "pm10"}
SAMPLE_FIELDS = [
    "route_id", "route_name", "method", "metric", "metric_class", "sample_index",
    "sample_count", "sample_lon", "sample_lat", "matched_location_type",
    "matched_location_id", "matched_location_name", "matched_lon", "matched_lat",
    "distance_km", "value", "category_value", "unit", "freshness", "observed_at",
    "as_of", "source_kind", "match_status",
]
SUMMARY_FIELDS = [
    "route_id", "route_name", "method", "metric", "metric_class", "sample_count",
    "matched_count", "coverage_ratio", "fresh_matched_count", "stale_matched_count",
    "fresh_coverage_ratio", "distinct_location_count", "mean_distance_km",
    "max_distance_km", "mean_numeric_value", "max_numeric_value",
]


def sample_route_points(coordinates: list[tuple[float, float]], spacing_km: float = 0.5) -> list[Coordinate]:
    """Place samples at cumulative spacing along every geometry segment, including endpoints."""
    if spacing_km <= 0 or len(coordinates) < 2:
        raise ValueError("A positive spacing and at least two route coordinates are required")
    points = [Coordinate(lon=coordinates[0][0], lat=coordinates[0][1])]
    traversed = 0.0
    next_distance = spacing_km
    for left_raw, right_raw in zip(coordinates, coordinates[1:]):
        left = Coordinate(lon=left_raw[0], lat=left_raw[1])
        right = Coordinate(lon=right_raw[0], lat=right_raw[1])
        segment_length = distance_km(left, right)
        if segment_length == 0:
            continue
        segment_end = traversed + segment_length
        while next_distance < segment_end - 1e-9:
            fraction = (next_distance - traversed) / segment_length
            points.append(Coordinate(lon=left.lon + (right.lon-left.lon)*fraction,
                                     lat=left.lat + (right.lat-left.lat)*fraction))
            next_distance += spacing_km
        traversed = segment_end
    end = Coordinate(lon=coordinates[-1][0], lat=coordinates[-1][1])
    if distance_km(points[-1], end) > 1e-9:
        points.append(end)
    elif len(points) == 1:
        points.append(end)
    return points


def _latest_observations(observations):
    latest = {}
    for observation in observations:
        key = (observation.source, observation.location_id, observation.metric)
        previous = latest.get(key)
        if previous is None or (observation.observed_at, observation.revision) > (previous.observed_at, previous.revision):
            latest[key] = observation
    return latest


def _is_usable(observation):
    return observation is not None and (observation.value is not None or observation.category_value is not None)


def compare_snapshot(repository, config, source_kind: str, as_of: datetime):
    """Evaluate all methods against one immutable repository snapshot."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Assessment time must include a timezone")
    routes = repository.load_routes()
    locations, observations, _logs = repository.environment_snapshot(source_kind, as_of)
    latest = _latest_observations(observations)
    location_map = {(location.source, location.location_id): location for location in locations}
    samples_out, summaries = [], []

    def append_comparison(route, method, metric, metric_class, points, *, regional_id=None, regional=False):
        _unit, _window, source = METRIC_SPECS[metric]
        rows = []
        if regional:
            # Region centres are separately labelled assignments, never station matches.
            points_for_rows = [(points[0], 1)]
        else:
            points_for_rows = [(point, index) for index, point in enumerate(points, 1)]
        for point, index in points_for_rows:
            selected = observation = None
            separation = None
            if regional:
                selected = location_map.get((source, regional_id))
                observation = latest.get((source, regional_id, metric))
                if not _is_usable(observation):
                    selected = observation = None
            else:
                usable = []
                for location in locations:
                    if location.source != source or location.location_type != "station":
                        continue
                    candidate = latest.get((source, location.location_id, metric))
                    if _is_usable(candidate):
                        age = (as_of - candidate.observed_at).total_seconds()
                        fresh = 0 <= age <= config.sources[source].stale_after_seconds
                        usable.append((location, candidate, fresh))
                fresh_candidates = [item for item in usable if item[2]]
                candidates = fresh_candidates or usable
                if candidates:
                    selected, observation, _fresh = min(
                        candidates,
                        key=lambda item: distance_km(point, Coordinate(lon=item[0].lon, lat=item[0].lat)),
                    )
                    separation = distance_km(point, Coordinate(lon=selected.lon, lat=selected.lat))
                    if separation > config.matching.station_max_distance_km:
                        selected = observation = None
            freshness = "missing"
            if _is_usable(observation):
                age = (as_of - observation.observed_at).total_seconds()
                freshness = "fresh" if 0 <= age <= config.sources[source].stale_after_seconds else "stale"
            rows.append({
                "route_id": route.route_id, "route_name": route.name, "method": method,
                "metric": metric, "metric_class": metric_class, "sample_index": index,
                "sample_count": len(points_for_rows), "sample_lon": point.lon, "sample_lat": point.lat,
                "matched_location_type": selected.location_type if selected else "",
                "matched_location_id": selected.location_id if selected else "",
                "matched_location_name": selected.name if selected else "",
                "matched_lon": selected.lon if selected else "", "matched_lat": selected.lat if selected else "",
                "distance_km": round(separation, 6) if separation is not None else "",
                "value": observation.value if observation else "",
                "category_value": observation.category_value if observation else "",
                "unit": observation.unit if observation else METRIC_SPECS[metric][0],
                "freshness": freshness, "observed_at": observation.observed_at.isoformat() if observation else "",
                "as_of": as_of.isoformat(), "source_kind": source_kind,
                "match_status": "matched" if selected else "missing",
            })
        samples_out.extend(rows)
        matched = [row for row in rows if row["match_status"] == "matched"]
        fresh_rows = [row for row in rows if row["freshness"] == "fresh"]
        stale_rows = [row for row in rows if row["freshness"] == "stale"]
        distances = [float(row["distance_km"]) for row in matched if row["distance_km"] != ""]
        values = [float(row["value"]) for row in matched if row["value"] not in ("", None)]
        summaries.append({
            "route_id": route.route_id, "route_name": route.name, "method": method,
            "metric": metric, "metric_class": metric_class, "sample_count": len(rows),
            "matched_count": len(matched), "coverage_ratio": round(len(matched)/len(rows), 6) if rows else 0,
            "fresh_matched_count": len(fresh_rows), "stale_matched_count": len(stale_rows),
            "fresh_coverage_ratio": round(len(fresh_rows)/len(rows), 6) if rows else 0,
            "distinct_location_count": len({row["matched_location_id"] for row in matched}),
            "mean_distance_km": round(statistics.mean(distances), 6) if distances else "",
            "max_distance_km": round(max(distances), 6) if distances else "",
            "mean_numeric_value": round(statistics.mean(values), 6) if values else "",
            "max_numeric_value": round(max(values), 6) if values else "",
        })

    for route in routes:
        coordinates = route.geometry.coordinates
        for method, points in (("nearest_start", [Coordinate(lon=coordinates[0][0], lat=coordinates[0][1])]),
                               ("nearest_end", [Coordinate(lon=coordinates[-1][0], lat=coordinates[-1][1])]),
                               ("along_route_500m", sample_route_points(coordinates))):
            for metric in METRIC_SPECS:
                if metric in REGIONAL_METRICS:
                    continue
                append_comparison(route, method, metric, "station", points)
        for metric in sorted(REGIONAL_METRICS):
            region_id = config.matching.route_regions.get(route.route_id)
            append_comparison(route, "regional_configured_assignment", metric, "region", [
                Coordinate(lon=coordinates[0][0], lat=coordinates[0][1])], regional_id=region_id, regional=True)
    return samples_out, summaries


def _write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--config", type=Path, default=ROOT / "config/environment.toml")
    parser.add_argument("--data-mode", choices=("demo", "live"), default="demo")
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 assessment time")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis/station_matching/results/demo")
    args = parser.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        parser.error("--as-of must include a timezone, for example +08:00 or Z")
    config = load_environment_config(args.config)
    repository = FileRepository(args.data_root)
    sample_rows, summary_rows = compare_snapshot(repository, config, args.data_mode, as_of)
    _write_csv(args.output_dir / "per_sample.csv", SAMPLE_FIELDS, sample_rows)
    _write_csv(args.output_dir / "summary.csv", SUMMARY_FIELDS, summary_rows)
    print(f"Wrote {len(sample_rows)} sample rows and {len(summary_rows)} summary rows to {args.output_dir}")
    print(f"source_kind={args.data_mode}; as_of={as_of.isoformat()}; observation snapshot read once")


if __name__ == "__main__":
    main()
