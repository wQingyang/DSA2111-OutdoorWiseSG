from types import SimpleNamespace
from fastapi.testclient import TestClient
from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT
from outdoorwise.difficulty.service import GenericDifficultyEstimator, label

def env(**values):
    return SimpleNamespace(metrics=[SimpleNamespace(metric=k, value=v, category_value=None) for k,v in values.items()])
def heat_env(category, **values):
    return SimpleNamespace(metrics=[SimpleNamespace(metric="heat_stress_level", value=None, category_value=category)] + [SimpleNamespace(metric=k, value=v, category_value=None) for k,v in values.items()])
def route(distance): return SimpleNamespace(route_id="r", distance_km=distance)

def test_generic_difficulty_bounds_and_components():
    estimator=GenericDifficultyEstimator(); low=estimator.predict(route(3),env()); high=estimator.predict(route(12),env(wbgt=34,relative_humidity=90,rainfall=10))
    assert 1 <= low.predicted_difficulty <= 5 and 1 <= high.predicted_difficulty <= 5
    assert high.predicted_difficulty > low.predicted_difficulty
    assert "distance" in low.components and low.available_feature_count == 1
    assert estimator.predict(route(5),env(wbgt=30)).components == estimator.predict(route(5),env(wbgt=30)).components
    assert label(1.8)=="Very easy" and label(2.6)=="Easy" and label(3.4)=="Moderate" and label(4.2)=="Hard" and label(5)=="Very hard"

def test_heat_hierarchy_does_not_double_count_correlated_signals():
    estimator = GenericDifficultyEstimator()
    wbgt = estimator.predict(route(5), env(wbgt=34, air_temperature=40, relative_humidity=100))
    assert set(wbgt.components) == {"distance", "wbgt"}
    category = estimator.predict(route(5), heat_env("High", air_temperature=40, relative_humidity=100))
    assert set(category.components) == {"distance", "heat_stress"}
    fallback = estimator.predict(route(5), env(air_temperature=40, relative_humidity=100))
    assert set(fallback.components) == {"distance", "temperature", "relative_humidity"}
    assert wbgt.predicted_difficulty == estimator.predict(route(5), env(wbgt=34, air_temperature=0, relative_humidity=0)).predicted_difficulty

def test_difficulty_api_and_invalid_route(tmp_path):
    import shutil
    shutil.copytree(ROOT/"data/catalog",tmp_path/"catalog")
    with TestClient(create_app(Settings(data_root=tmp_path,data_mode="demo"))) as client:
        assert client.get("/api/routes/unknown/difficulty").status_code == 404
        result=client.get("/api/routes/marina_bay/difficulty")
        assert result.status_code == 200 and 1 <= result.json()["predicted_difficulty"] <= 5
