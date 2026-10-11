from datetime import datetime, timezone

from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT


def test_personalization_api_and_errors(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode="live"))) as client:
        payload = {"route_id": "route-a", "completed_at": datetime.now(timezone.utc).isoformat(),
                   "actual_distance_km": 5, "actual_duration_min": 30}
        created = client.post("/api/users/alice/runs", json=payload)
        assert created.status_code == 201
        run = created.json()
        assert run["average_pace_min_per_km"] == 6
        assert client.get("/api/users/bob/runs").json() == []
        assert client.get(f"/api/users/alice/runs/{run['completed_run_id']}").status_code == 200
        assert client.get("/api/users/alice/runs/missing").status_code == 404

        assert client.put("/api/users/alice/favourites/route-a").status_code == 200
        assert client.put("/api/users/alice/favourites/route-a").status_code == 200
        assert len(client.get("/api/users/alice/favourites").json()) == 1
        assert client.delete("/api/users/alice/favourites/route-a").status_code == 204
        assert client.delete("/api/users/alice/favourites/route-a").status_code == 404

        feedback_url = f"/api/users/alice/runs/{run['completed_run_id']}/feedback"
        assert client.post(feedback_url, json={"difficulty": 6}).status_code == 422
        feedback = client.post(feedback_url, json={"difficulty": 4, "tags": ["too_hilly"]})
        assert feedback.status_code == 201
        assert feedback.json()["route_id"] == "route-a"
        assert client.post("/api/users/bob/runs/missing/feedback", json={"difficulty": 3}).status_code == 404
