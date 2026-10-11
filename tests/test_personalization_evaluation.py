from datetime import datetime, timedelta, timezone
from outdoorwise.evaluation.personalization import evaluate
from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback

def run(i,generic,user="u"):
    return CompletedRun(completed_run_id=f"r{i}{user}",user_id=user,route_id="r",completed_at=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=i),actual_distance_km=5,actual_duration_min=30,predicted_difficulty=generic)
def feedback(i,diff,user="u"):
    return DifficultyFeedback(feedback_id=f"f{i}{user}",user_id=user,route_id="r",completed_run_id=f"r{i}{user}",difficulty=diff,created_at=datetime.now(timezone.utc))

def test_chronological_replay_and_metrics():
    result=evaluate([run(0,3),run(1,3),run(2,3)],[feedback(0,4),feedback(1,4),feedback(2,2)])
    assert result["overall"]["observation_count"]==3
    assert result["raw_predictions"][0]["prior_history_count"]==0
    assert result["raw_predictions"][1]["prior_history_count"]==1
    assert result["raw_predictions"][2]["prior_history_count"]==2
    assert result["overall"]["generic"]["mae"]==1

def test_missing_data_user_isolation_and_determinism():
    runs=[run(0,3,"a"),run(0,None,"b")]
    result=evaluate([runs[0]],[feedback(0,4,"a")]); again=evaluate([runs[0]],[feedback(0,4,"a")])
    assert result==again and result["overall"]["user_count"]==1
    skipped=evaluate([run(0,3),run(1,3)],[feedback(0,4)])
    assert skipped["skipped"]["reasons"]["missing_feedback"]==1
