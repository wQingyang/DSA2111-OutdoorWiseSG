from types import SimpleNamespace
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
