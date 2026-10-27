from math import atan2, cos, radians, sin, sqrt

from outdoorwise.contracts.core import Coordinate
from outdoorwise.contracts.environment import METRIC_SPECS, RouteEnvironment, RouteMetric, utc_now
from outdoorwise.contracts.geo import distance_km


HEAT_ORDER = {"Low": 0, "Moderate": 1, "High": 2}


def sample_geometry(coordinates, spacing_km=.5, maximum=30):
    """Return approximately evenly spaced points, including the route start/end."""
    points = [Coordinate(lon=coordinates[0][0], lat=coordinates[0][1])]
    carry = 0.0
    for left_raw, right_raw in zip(coordinates, coordinates[1:]):
        left = Coordinate(lon=left_raw[0], lat=left_raw[1]); right = Coordinate(lon=right_raw[0], lat=right_raw[1])
        segment = distance_km(left, right)
        while segment > 0 and carry + segment >= spacing_km and len(points) < maximum - 1:
            fraction = (spacing_km - carry) / segment
            left = Coordinate(lon=left.lon + (right.lon - left.lon) * fraction,
                              lat=left.lat + (right.lat - left.lat) * fraction)
            points.append(left); segment = distance_km(left, right); carry = 0.0
        carry += segment
    end = Coordinate(lon=coordinates[-1][0], lat=coordinates[-1][1])
    if distance_km(points[-1], end) > .01:
        points.append(end)
    return points


class DynamicRouteEnvironmentService:
    """Matches stored observations to samples along arbitrary generated geometry."""
    def __init__(self, repository, config, source_kind):
        self.repository = repository; self.config = config; self.source_kind = source_kind

    def evaluate(self, route, as_of=None):
        as_of = as_of or utc_now()
        locations, observations, logs = self.repository.environment_snapshot(self.source_kind, as_of)
        latest = {}
        for observation in observations:
            key = (observation.source, observation.location_id, observation.metric)
            if key not in latest or (observation.observed_at, observation.revision) > (latest[key].observed_at, latest[key].revision):
                latest[key] = observation
        last_ingestion = {}
        for log in logs:
            if log.status != "skipped" and (log.source not in last_ingestion or log.finished_at > last_ingestion[log.source].finished_at):
                last_ingestion[log.source] = log
        samples = sample_geometry(route.geometry.coordinates)
        metrics = []
        for metric, (unit, window, source) in METRIC_SPECS.items():
            regional = metric in {"pm25", "psi", "pm10"}
            matched = []
            for point in samples:
                candidates = [location for location in locations if location.source == source and
                              location.location_type == ("region" if regional else "station") and
                              (source, location.location_id, metric) in latest]
                usable = [location for location in candidates if latest[(source, location.location_id, metric)].value is not None or
                          latest[(source, location.location_id, metric)].category_value is not None]
                fresh = [location for location in usable if 0 <= (as_of - latest[(source, location.location_id, metric)].observed_at).total_seconds()
                         <= self.config.sources[source].stale_after_seconds]
                usable = fresh or usable
                if not usable:
                    continue
                selected = min(usable, key=lambda location: distance_km(point, Coordinate(lon=location.lon, lat=location.lat)))
                separation = distance_km(point, Coordinate(lon=selected.lon, lat=selected.lat))
                if not regional and separation > self.config.matching.station_max_distance_km:
                    continue
                matched.append((selected, latest[(source, selected.location_id, metric)], separation, point))
            if matched:
                if metric == "heat_stress_level":
                    selected, observation, separation, selected_point = max(matched, key=lambda item: HEAT_ORDER.get(item[1].category_value, -1))
                elif metric == "wind_direction":
                    selected, observation, separation, selected_point = matched[len(matched) // 2]
                else:
                    selected, observation, separation, selected_point = max(matched, key=lambda item: item[1].value)
                states = ["fresh" if 0 <= (as_of-item[1].observed_at).total_seconds() <= self.config.sources[source].stale_after_seconds else "stale" for item in matched]
                state = "stale" if "stale" in states else "fresh"
                failed = source in last_ingestion and last_ingestion[source].status == "failed"
                cached = failed or any((as_of-item[1].fetched_at).total_seconds() > self.config.sources[source].interval_seconds for item in matched)
                delivery = "demo" if self.source_kind == "demo" else ("cache" if cached else "live")
                unique_locations = len({item[0].location_id for item in matched})
                reason = (f"Matched {len(matched)}/{len(samples)} route samples across {unique_locations} source location(s); "
                          f"the displayed value is conservative along-route aggregation. Aggregate observation/fetch times are the oldest matched times; individual source times are in sample provenance.")
                value = observation.value; category = observation.category_value
                location_id = selected.location_id; location_name = selected.name
                station_distance = max(item[2] for item in matched) if not regional else None
                observed_at = min(item[1].observed_at for item in matched)
                fetched_at = min(item[1].fetched_at for item in matched)
                source_updated = observation.source_updated_at; revision = observation.revision
            else:
                value = category = location_id = location_name = observed_at = fetched_at = source_updated = revision = None
                station_distance = None; state = "missing"; delivery = "unavailable"
                reason = f"No usable observation matched any of {len(samples)} route samples."
            metrics.append(RouteMetric(route_id=route.route_id, metric=metric, value=value, category_value=category,
                unit=unit, aggregation_window=window, source=source, location_id=location_id, location_name=location_name,
                source_kind=self.source_kind, delivery=delivery, state=state,
                match_method="along_route_sampling_500m_v1", station_distance_km=round(station_distance, 3) if station_distance is not None else None,
                observed_at=observed_at, source_updated_at=source_updated, fetched_at=fetched_at, as_of=as_of,
                revision=revision, reason=reason, sample_count=len(samples), matched_sample_count=len(matched),
                sample_provenance=[dict(sample_lat=item[3].lat, sample_lon=item[3].lon, location_id=item[0].location_id, source=source,
                    distance_km=round(item[2], 3), observed_at=item[1].observed_at.isoformat(),
                    first_fetched_at=(item[1].first_fetched_at or item[1].fetched_at).isoformat(),
                    source_updated_at=item[1].source_updated_at.isoformat() if item[1].source_updated_at else None,
                    revision=item[1].revision) for item in matched]))
        return RouteEnvironment(route_id=route.route_id, as_of=as_of, metrics=metrics)
