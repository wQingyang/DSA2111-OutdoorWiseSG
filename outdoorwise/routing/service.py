from datetime import datetime, timedelta, timezone
from hashlib import sha256
import httpx

from outdoorwise.contracts.core import Coordinate
from outdoorwise.contracts.geo import distance_km
from outdoorwise.contracts.models import LineString

from .models import GeneratedRoute, RouteGenerationRequest, RouteGenerationResponse


class DynamicRouteService:
    def __init__(self, client, repository):
        self.client = client
        self.repository = repository

    @staticmethod
    def _coordinates(payload: dict) -> list[tuple[float, float]]:
        features = payload.get("features") or []
        if not features:
            raise ValueError("Routing provider returned no route")
        coordinates = features[0].get("geometry", {}).get("coordinates") or []
        if len(coordinates) < 2:
            raise ValueError("Routing provider returned an invalid route geometry")
        return [(float(point[0]), float(point[1])) for point in coordinates]

    @staticmethod
    def _distance(payload: dict, coordinates: list[tuple[float, float]]) -> float:
        summary = (payload["features"][0].get("properties", {}).get("summary") or {})
        if summary.get("distance") is not None:
            return float(summary["distance"]) / 1000
        return sum(distance_km(Coordinate(lon=a[0], lat=a[1]), Coordinate(lon=b[0], lat=b[1])) for a, b in zip(coordinates, coordinates[1:]))

    @staticmethod
    def _overlap(a: GeneratedRoute, b: GeneratedRoute) -> float:
        def cells(route):
            return {(round(lon, 3), round(lat, 3)) for lon, lat in route.geometry.coordinates}
        left, right = cells(a), cells(b)
        return len(left & right) / max(1, min(len(left), len(right)))

    def generate(self, request: RouteGenerationRequest) -> RouteGenerationResponse:
        accepted: list[GeneratedRoute] = []
        rejected = 0
        rejection_reasons: dict[str, int] = {}
        now = datetime.now(timezone.utc)
        attempts = min(15, max(6, request.candidate_count * 3))
        for seed in range(1, attempts + 1):
            try:
                payload = self.client.round_trip(request, seed)
                coordinates = self._coordinates(payload)
                actual = self._distance(payload, coordinates)
                error = abs(actual - request.target_distance_km) / request.target_distance_km * 100
                if error > request.distance_tolerance_pct:
                    adjusted_length = max(250, request.target_distance_km * 1000 * request.target_distance_km / actual)
                    payload = self.client.round_trip(request, seed, length_m=adjusted_length)
                    coordinates = self._coordinates(payload)
                    actual = self._distance(payload, coordinates)
                    error = abs(actual - request.target_distance_km) / request.target_distance_km * 100
                start = request.start
                if distance_km(start, Coordinate(lon=coordinates[0][0], lat=coordinates[0][1])) > .25:
                    raise ValueError("Route does not start near the requested point")
                if distance_km(Coordinate(lon=coordinates[0][0], lat=coordinates[0][1]), Coordinate(lon=coordinates[-1][0], lat=coordinates[-1][1])) > .2:
                    raise ValueError("Route is not a closed loop")
                if error > request.distance_tolerance_pct:
                    raise ValueError("Route is outside the requested distance tolerance")
                digest = sha256(f"{start.lon}:{start.lat}:{request.target_distance_km}:{seed}:{coordinates}".encode()).hexdigest()[:16]
                route = GeneratedRoute(
                    route_id=f"generated_{digest}", name=f"Generated {actual:.1f} km loop",
                    distance_km=round(actual, 3), target_distance_km=request.target_distance_km,
                    distance_error_pct=round(error, 1), geometry=LineString(coordinates=coordinates),
                    seed=seed, created_at=now, expires_at=now + timedelta(days=7),
                    warnings=["Automatically generated from OpenStreetMap data; confirm current on-site access before running."],
                )
                if any(self._overlap(route, other) >= .8 for other in accepted):
                    raise ValueError("Route is too similar to an accepted candidate")
                accepted.append(route)
                if len(accepted) == request.candidate_count:
                    break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                rejected += 1
                reason = "Routing provider could not find a loop for this direction"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                rejected += 1
                reason = str(exc) or exc.__class__.__name__
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        if accepted:
            self.repository.save_all(accepted)
        warnings = [] if len(accepted) == request.candidate_count else ["Fewer distinct routes met the requested constraints."]
        return RouteGenerationResponse(candidates=accepted, rejected_count=rejected,
                                       rejection_reasons=rejection_reasons, warnings=warnings)
