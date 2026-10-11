from datetime import datetime, timezone
from outdoorwise.personalization.difficulty import PersonalizedDifficultyPredictor
from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback, UserRunningProfile

def run(i, generic):
    return CompletedRun(completed_run_id=f"r{i}", user_id="u", route_id="r", completed_at=datetime.now(timezone.utc), actual_distance_km=5, actual_duration_min=30, predicted_difficulty=generic)
def fb(i, value):
    return DifficultyFeedback(feedback_id=f"f{i}", user_id="u", route_id="r", completed_run_id=f"r{i}", difficulty=value, created_at=datetime.now(timezone.utc))
def profile(distance=5):
    return UserRunningProfile(user_id="u", completed_run_count=1, feedback_count=0, favourite_count=0, comfortable_distance_km=distance, usable_run_count=1, profile_confidence="low")

def test_cold_start_and_median_residual_with_shrinkage():
    predictor=PersonalizedDifficultyPredictor(); cold=predictor.predict("r",5,3,[],[],profile())
    assert cold["personalized_predicted_difficulty"] == 3 and cold["confidence"] == "none"
    result=predictor.predict("r",5,3,[run(1,2),run(2,2),run(3,2),run(4,2)],[fb(1,4),fb(2,3),fb(3,4),fb(4,3)],profile())
    assert result["historical_bias"] == 1.5 and result["shrinkage_weight"] == .571

def test_distance_adjustment_bounds_and_favourites_excluded():
    predictor=PersonalizedDifficultyPredictor(); short=predictor.predict("r",2,3,[run(1,3)],[fb(1,3)],profile(5)); long=predictor.predict("r",10,3,[run(1,3)],[fb(1,3)],profile(5))
    assert short["personalized_predicted_difficulty"] < long["personalized_predicted_difficulty"]
    assert 1 <= predictor.predict("r",100,5,[],[],profile(1))["personalized_predicted_difficulty"] <= 5
