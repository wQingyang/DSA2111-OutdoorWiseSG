from datetime import datetime, timedelta, timezone

from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback, FavouriteRoute
from outdoorwise.personalization.profile import derive_running_profile
from fastapi.testclient import TestClient
from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(i, distance, pace=None):
    return CompletedRun(completed_run_id=f"r{i}", user_id="u", route_id="route",
        completed_at=BASE + timedelta(days=i), actual_distance_km=distance,
        actual_duration_min=distance * pace if pace else 30, average_pace_min_per_km=pace)


def feedback(i, difficulty):
    return DifficultyFeedback(feedback_id=f"f{i}", user_id="u", route_id="route",
        completed_run_id=f"r{i}", difficulty=difficulty, created_at=BASE + timedelta(days=i))


def test_empty_and_one_run_profiles():
    empty = derive_running_profile("u", [], [], [])
    assert empty.profile_confidence == "none" and empty.total_distance_km is None
    profile = derive_running_profile("u", [run(1, 5, 6)], [], [])
    assert profile.completed_run_count == 1 and profile.mean_pace_min_per_km == 6
    assert profile.typical_distance_min_km == profile.typical_distance_max_km == 5
    assert profile.profile_confidence == "low"


def test_aggregates_recent_mean_and_quartile_range():
    profile = derive_running_profile("u", [run(i, d, 5 + i / 10) for i, d in enumerate([2, 4, 6, 8, 10, 12, 14])], [], [])
    assert profile.mean_distance_km == 8 and profile.median_distance_km == 8
    assert profile.recent_mean_distance_km == 10
    assert profile.typical_distance_min_km == 5 and profile.typical_distance_max_km == 11
    assert profile.mean_pace_min_per_km == 5.3
    assert profile.profile_confidence == "high"


def test_comfortable_distance_uses_only_easy_and_just_right():
    runs = [run(i, d) for i, d in enumerate([3, 5, 7, 9, 11])]
    profile = derive_running_profile("u", runs, [feedback(0, 1), feedback(1, 2), feedback(2, 3), feedback(3, 4), feedback(4, 5)], [])
    assert profile.comfortable_distance_km == 6


def test_difficulty_trends_and_favourites():
    runs = [run(i, 5) for i in range(6)]
    fav = [FavouriteRoute(user_id="u", route_id="route", created_at=BASE)]
    assert derive_running_profile("u", runs, [feedback(i, 1 + i // 2) for i in range(6)], fav).recent_difficulty_trend == "increasing"
    assert derive_running_profile("u", runs, [feedback(i, 5 - i // 2) for i in range(6)], []).recent_difficulty_trend == "decreasing"
    assert derive_running_profile("u", runs, [feedback(i, 3) for i in range(6)], []).recent_difficulty_trend == "stable"
    assert derive_running_profile("u", runs, [feedback(0, 3), feedback(1, 4)], []).recent_difficulty_trend == "insufficient_data"
    assert derive_running_profile("u", runs, [], fav).favourite_count == 1


def test_running_profile_api_requires_auth_and_supports_empty_history(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode="live"))) as client:
        assert client.get("/api/me/running-profile").status_code == 401
        assert client.post("/api/auth/register", json={"username": "profile_user", "password": "password123"}).status_code == 201
        result = client.get("/api/me/running-profile")
        assert result.status_code == 200
        assert result.json()["profile_confidence"] == "none"
        assert result.json()["completed_run_count"] == 0
