import httpx

from .models import RouteGenerationRequest


class OpenRouteServiceClient:
    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client

    def round_trip(self, request: RouteGenerationRequest, seed: int, length_m: float | None = None) -> dict:
        if not self.api_key:
            raise RuntimeError("Dynamic routing is not configured. Set ORS_API_KEY on the server.")
        weighting = {}
        if request.preferences.prefer_green:
            weighting["green"] = 0.8
        if request.preferences.prefer_quiet:
            weighting["quiet"] = 1.0
        options: dict = {"round_trip": {"length": length_m or request.target_distance_km * 1000, "points": 4, "seed": seed}}
        if request.preferences.avoid_steps:
            options["avoid_features"] = ["steps"]
        if weighting:
            options["profile_params"] = {"weightings": weighting}
        payload = {
            "coordinates": [[request.start.lon, request.start.lat]],
            "instructions": False,
            "elevation": False,
            "options": options,
        }
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        if self.client:
            response = self.client.post(f"{self.base_url}/v2/directions/foot-walking/geojson", headers=headers, json=payload)
        else:
            with httpx.Client(timeout=30) as client:
                response = client.post(f"{self.base_url}/v2/directions/foot-walking/geojson", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

