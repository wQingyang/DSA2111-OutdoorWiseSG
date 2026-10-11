from datetime import datetime, timezone

from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT


def test_personalization_api_and_errors(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode="live"))) as client:
        assert client.post("/api/auth/register", json={"username": "alice", "password": "correct horse"}).status_code == 201
        user_id = client.get("/api/auth/me").json()["user_id"]
        payload = {"route_id": "route-a", "completed_at": datetime.now(timezone.utc).isoformat(),
                   "actual_distance_km": 5, "actual_duration_min": 30}
        created = client.post(f"/api/users/{user_id}/runs", json=payload)
        assert created.status_code == 201
        run = created.json()
        assert run["average_pace_min_per_km"] == 6
        assert client.get("/api/users/bob/runs").status_code == 403
        assert client.get(f"/api/users/{user_id}/runs/{run['completed_run_id']}").status_code == 200
        assert client.get(f"/api/users/{user_id}/runs/missing").status_code == 404

        assert client.put(f"/api/users/{user_id}/favourites/route-a").status_code == 200
        assert client.put(f"/api/users/{user_id}/favourites/route-a").status_code == 200
        assert len(client.get(f"/api/users/{user_id}/favourites").json()) == 1
        assert client.delete(f"/api/users/{user_id}/favourites/route-a").status_code == 204
        assert client.delete(f"/api/users/{user_id}/favourites/route-a").status_code == 404

        feedback_url = f"/api/users/{user_id}/runs/{run['completed_run_id']}/feedback"
        assert client.post(feedback_url, json={"difficulty": 6}).status_code == 422
        feedback = client.post(feedback_url, json={"difficulty": 4, "tags": ["too_hilly"]})
        assert feedback.status_code == 201
        assert feedback.json()["route_id"] == "route-a"
        assert client.post(f"/api/users/{user_id}/runs/missing/feedback", json={"difficulty": 3}).status_code == 404
