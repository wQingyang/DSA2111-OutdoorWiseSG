from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT


def client_for(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    return TestClient(create_app(Settings(data_root=tmp_path, data_mode="live")))


def test_registration_hashing_login_me_logout_and_isolation(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/register", json={"username": "Runner", "password": "password123"}).status_code == 201
        assert client.get("/api/auth/me").json()["username"] == "Runner"
        assert client.post("/api/auth/register", json={"username": "runner", "password": "password123"}).status_code == 409
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"username": "RUNNER", "password": "wrongpass"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "runner", "password": "password123"}).status_code == 200
        users = client.get("/api/auth/me").json()
        assert users["user_id"]
        assert client.get(f"/api/users/{users['user_id']}/runs").status_code == 200
        assert client.get("/api/users/someone-else/runs").status_code == 403
        db_text = (tmp_path / "runtime/accounts.sqlite3").read_bytes()
        assert b"password123" not in db_text


def test_registration_validation_and_availability(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/auth/username-availability?username=valid_user").json()["available"] is True
        assert client.post("/api/auth/register", json={"username": "ab", "password": "password123"}).status_code == 422
        assert client.post("/api/auth/register", json={"username": "valid_user", "password": "short"}).status_code == 422
