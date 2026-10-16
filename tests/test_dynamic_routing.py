import json
import shutil

import httpx
from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.config import ROOT, Settings
from outdoorwise.routing.models import RouteGenerationRequest
from outdoorwise.routing.ors_client import OpenRouteServiceClient
from outdoorwise.routing.repository import GeneratedRouteRepository
from outdoorwise.routing.service import DynamicRouteService
from outdoorwise.routing.environment import sample_geometry


def route_payload(distance=5000, offset=0):
    lon, lat = 103.7764, 1.2966
    coordinates = [[lon, lat], [lon + .01 + offset, lat], [lon + .01 + offset, lat + .01], [lon, lat + .01], [lon, lat]]
    return {"features": [{"geometry": {"type": "LineString", "coordinates": coordinates}, "properties": {"summary": {"distance": distance}}}]}


class StubRoutingClient:
    def round_trip(self, request, seed, length_m=None):
        return route_payload(5000 + seed * 10, seed * .003)


def generation_request():
    return RouteGenerationRequest(start={"lon": 103.7764, "lat": 1.2966}, target_distance_km=5, candidate_count=2)


def test_ors_request_uses_round_trip_and_preferences():
    def handler(incoming):
        assert incoming.url.path.endswith("/v2/directions/foot-walking/geojson")
        assert incoming.headers["Authorization"] == "secret"
        body = json.loads(incoming.content)
        assert body["options"]["round_trip"]["length"] == 5000
        assert body["options"]["avoid_features"] == ["steps"]
        assert body["options"]["profile_params"]["weightings"] == {"green": .8, "quiet": 1.0}
        return httpx.Response(200, json=route_payload())
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert OpenRouteServiceClient("https://routing.example", "secret", client).round_trip(generation_request(), 7)["features"]


def test_generation_retries_with_calibrated_length(tmp_path):
    class LongFirstRouteClient:
        def __init__(self): self.lengths = []
        def round_trip(self, request, seed, length_m=None):
            self.lengths.append(length_m)
            return route_payload(8000 if length_m is None else 5050, seed * .003)

    client = LongFirstRouteClient()
    result = DynamicRouteService(client, GeneratedRouteRepository(tmp_path)).generate(
        generation_request().model_copy(update={"candidate_count": 1}))
    assert len(result.candidates) == 1
    assert client.lengths[:2] == [None, 3125]


def test_generation_continues_after_provider_cannot_find_one_loop(tmp_path):
    class MissingFirstLoopClient:
        def round_trip(self, request, seed, length_m=None):
            if seed == 1:
                response = httpx.Response(404, request=httpx.Request("POST", "https://api.heigit.org"),
                                          json={"error": {"message": "Route could not be found"}})
                raise httpx.HTTPStatusError("missing", request=response.request, response=response)
            return route_payload(5000, seed * .003)

    result = DynamicRouteService(MissingFirstLoopClient(), GeneratedRouteRepository(tmp_path)).generate(
        generation_request().model_copy(update={"candidate_count": 1}))
    assert len(result.candidates) == 1
    assert result.rejected_count == 1
    assert result.rejection_reasons["Routing provider could not find a loop for this direction"] == 1


def test_generation_validates_and_persists(tmp_path):
    repository = GeneratedRouteRepository(tmp_path)
    result = DynamicRouteService(StubRoutingClient(), repository).generate(generation_request())
    assert len(result.candidates) == 2
    assert all(item.distance_error_pct < 1 for item in result.candidates)
    assert repository.get(result.candidates[0].route_id) == result.candidates[0]


def test_dynamic_route_api_and_gpx(tmp_path):
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    settings = Settings(data_root=tmp_path, environment_config=ROOT / "config/environment.toml", data_mode="demo")
    app = create_app(settings)
    app.state.dynamic_routes = DynamicRouteService(StubRoutingClient(), app.state.generated_route_repository)
    with TestClient(app) as client:
        response = client.post("/api/generated-routes", json=generation_request().model_dump(mode="json"))
        assert response.status_code == 200
        assert len(response.json()["assessments"]) == 2
        assert len(response.json()["assessments"][0]["environment"]["metrics"]) == 10
        assert 1 <= response.json()["assessments"][0]["generic_difficulty"]["predicted_difficulty"] <= 5
        assert response.json()["assessments"][0]["rank"] == 1
        route_id = response.json()["candidates"][0]["route_id"]
        assert client.get(f"/api/generated-routes/{route_id}").status_code == 200
        gpx = client.get(f"/api/generated-routes/{route_id}/export.gpx")
        assert gpx.status_code == 200
        assert b"<trkpt" in gpx.content


def test_unconfigured_routing_returns_503(tmp_path):
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    settings = Settings(data_root=tmp_path, environment_config=ROOT / "config/environment.toml", data_mode="demo")
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/generated-routes", json=generation_request().model_dump(mode="json"))
    assert response.status_code == 503
    assert "ORS_API_KEY" in response.json()["detail"]


def test_rejected_routing_key_has_specific_error(tmp_path):
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    settings = Settings(data_root=tmp_path, environment_config=ROOT / "config/environment.toml", data_mode="demo")
    app = create_app(settings)

    class RejectedClient:
        def round_trip(self, request, seed, length_m=None):
            response = httpx.Response(401, request=httpx.Request("POST", "https://api.heigit.org"))
            raise httpx.HTTPStatusError("rejected", request=response.request, response=response)

    app.state.dynamic_routes = DynamicRouteService(RejectedClient(), app.state.generated_route_repository)
    with TestClient(app) as client:
        response = client.post("/api/generated-routes", json=generation_request().model_dump(mode="json"))
    assert response.status_code == 502
    assert "key was rejected" in response.json()["detail"]


def test_provider_validation_message_is_returned_without_headers(tmp_path):
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    settings = Settings(data_root=tmp_path, environment_config=ROOT / "config/environment.toml", data_mode="demo")
    app = create_app(settings)

    class InvalidRequestClient:
        def round_trip(self, request, seed, length_m=None):
            response = httpx.Response(400, request=httpx.Request("POST", "https://api.heigit.org", headers={"Authorization": "secret"}),
                                      json={"error": {"code": 2010, "message": "Unable to find a routable point"}})
            raise httpx.HTTPStatusError("invalid", request=response.request, response=response)

    app.state.dynamic_routes = DynamicRouteService(InvalidRequestClient(), app.state.generated_route_repository)
    with TestClient(app) as client:
        response = client.post("/api/generated-routes", json=generation_request().model_dump(mode="json"))
    detail = response.json()["detail"]
    assert "Unable to find a routable point" in detail
    assert "secret" not in detail


def test_geometry_sampling_includes_intermediate_points():
    points = sample_geometry([(103.77, 1.29), (103.79, 1.29)], spacing_km=.5)
    assert len(points) >= 5
    assert points[0].lon == 103.77
    assert points[-1].lon == 103.79
