from types import SimpleNamespace
from outdoorwise.personalization.ranking import rank_candidates
from fastapi.testclient import TestClient
from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT

def rec(route, score): return SimpleNamespace(route_id=route, score=score)
def pred(route, difficulty): return {"route_id":route,"generic_predicted_difficulty":difficulty,"personalized_predicted_difficulty":difficulty,"confidence":"none"}

def test_target_changes_order_and_candidate_set_is_preserved():
    candidates=[rec("easy",90),rec("hard",90)]
    assert [x["route_id"] for x in rank_candidates(candidates,[pred("easy",2),pred("hard",5)],2)] == ["easy","hard"]
    assert {x["route_id"] for x in rank_candidates(candidates,[pred("easy",2),pred("hard",5)],5)} == {"easy","hard"}

def test_base_score_and_deterministic_ties_are_preserved():
    result=rank_candidates([rec("b",50),rec("a",50)],[pred("b",3),pred("a",3)],3)
    assert [x["route_id"] for x in result] == ["b","a"]
    assert all(x["original_base_rank"] in {1,2} and x["personalized_rank"] in {1,2} for x in result)

def test_authenticated_endpoint_and_anonymous_flow(tmp_path):
    import shutil
    shutil.copytree(ROOT/"data/catalog", tmp_path/"catalog")
    with TestClient(create_app(Settings(data_root=tmp_path,data_mode="demo"))) as client:
        assert client.post("/api/me/recommendations", json={"target_difficulty":3}).status_code == 401
        assert client.post("/api/auth/register", json={"username":"ranker","password":"password123"}).status_code == 201
        result=client.post("/api/me/recommendations", json={"target_difficulty":3})
        assert result.status_code == 200 and set(result.json()) == {"run","target_difficulty","recommendations"}
        assert client.post("/api/recommendations", json={}).status_code == 200
