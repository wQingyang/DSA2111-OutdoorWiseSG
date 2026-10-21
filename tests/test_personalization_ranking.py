from types import SimpleNamespace
from datetime import datetime, timezone
from outdoorwise.personalization.ranking import rank_candidates
from fastapi.testclient import TestClient
from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT

def rec(route, score): return SimpleNamespace(route_id=route, score=score)
def pred(route, difficulty): return {"route_id":route,"generic_predicted_difficulty":difficulty,"personalized_predicted_difficulty":difficulty,"confidence":"none"}

def test_target_changes_order_and_candidate_set_is_preserved():
    candidates=[rec("easy",90),rec("hard",90)]
    easy_target=rank_candidates(candidates,[pred("easy",2),pred("hard",5)],2)
    assert [x["route_id"] for x in easy_target] == ["easy","hard"]
    result=rank_candidates(candidates,[pred("easy",2),pred("hard",5)],5)
    assert [x["route_id"] for x in result] == ["hard","easy"]
    assert {x["route_id"] for x in result} == {"easy","hard"}
    assert {x["route_id"]:x["original_base_rank"] for x in easy_target} == {x["route_id"]:x["original_base_rank"] for x in result}
    assert {x["route_id"]:x["generic_difficulty"] for x in easy_target} == {x["route_id"]:x["generic_difficulty"] for x in result}
    assert {x["route_id"]:x["personalized_difficulty"] for x in easy_target} == {x["route_id"]:x["personalized_difficulty"] for x in result}

def test_base_score_and_deterministic_ties_are_preserved():
    result=rank_candidates([rec("b",50),rec("a",50)],[pred("b",3),pred("a",3)],3)
    assert [x["route_id"] for x in result] == ["b","a"]
    assert all(x["original_base_rank"] in {1,2} and x["personalized_rank"] in {1,2} for x in result)

def test_original_rank_resolves_equal_mismatch_and_score_is_exposed():
    result=rank_candidates([rec("first",80),rec("second",100)],[pred("first",2),pred("second",4)],3)
    assert [x["route_id"] for x in result] == ["first","second"]
    assert result[0]["base_recommendation_score"] == 80
    assert result[0]["personalized_score"] == -1

def test_authenticated_endpoint_and_anonymous_flow(tmp_path):
    import shutil
    shutil.copytree(ROOT/"data/catalog", tmp_path/"catalog")
    with TestClient(create_app(Settings(data_root=tmp_path,data_mode="demo"))) as client:
        assert client.post("/api/me/recommendations", json={"target_difficulty":3}).status_code == 401
        assert client.post("/api/auth/register", json={"username":"ranker","password":"password123"}).status_code == 201
        result=client.post("/api/me/recommendations", json={"target_difficulty":3})
        assert result.status_code == 200 and set(result.json()) == {"run","target_difficulty","recommendations"}
        assert client.post("/api/recommendations", json={}).status_code == 200


def test_user_history_does_not_change_shared_ranking(tmp_path):
    import shutil
    shutil.copytree(ROOT / "data/catalog", tmp_path / "catalog")
    payload = {"target_distance_km": 4, "duration_min": 30, "horizon_min": 30,
               "target_difficulty": 3, "location": None, "max_access_distance_km": None}
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode="demo"))) as client:
        users = {}
        for username, feedback in (("historyhigh", 5), ("historylow", 1)):
            response = client.post("/api/auth/register", json={"username": username, "password": "password123"})
            users[username] = response.json()["user_id"]
            run = client.post(f"/api/users/{users[username]}/runs", json={
                "route_id": "marina_bay", "completed_at": datetime.now(timezone.utc).isoformat(),
                "actual_distance_km": 4, "actual_duration_min": 30, "predicted_difficulty": 2,
            }).json()
            assert client.post(f"/api/users/{users[username]}/runs/{run['completed_run_id']}/feedback",
                               json={"difficulty": feedback}).status_code == 201

        results = {}
        for username in users:
            assert client.post("/api/auth/login", json={"username": username, "password": "password123"}).status_code == 200
            response = client.post("/api/me/recommendations", json=payload)
            assert response.status_code == 200
            results[username] = response.json()

        shared_a = {row["route_id"]: row for row in results["historyhigh"]["run"]["recommendations"]}
        shared_b = {row["route_id"]: row for row in results["historylow"]["run"]["recommendations"]}
        assert set(shared_a) == set(shared_b)
        for route_id in shared_a:
            assert {key: shared_a[route_id][key] for key in ("risk_score", "score", "recommendation_score", "original_base_rank", "final_rank")} == {
                key: shared_b[route_id][key] for key in ("risk_score", "score", "recommendation_score", "original_base_rank", "final_rank")}

        personal_a = {row["route_id"]: row for row in results["historyhigh"]["recommendations"]}
        personal_b = {row["route_id"]: row for row in results["historylow"]["recommendations"]}
        assert any(personal_a[route_id]["personalized_difficulty"] != personal_b[route_id]["personalized_difficulty"] for route_id in personal_a)
        assert all(personal_a[route_id]["pipeline_rank"] == shared_a[route_id]["final_rank"] for route_id in personal_a)
