import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback

PATTERNS = {"underestimates": (6, 2, 4), "overestimates": (6, 4, 2), "accurate": (6, 3, 3), "sparse": (2, 3, 4)}

def generate(output_dir):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc); runs=[]; feedback=[]
    for user, (count, generic, actual) in PATTERNS.items():
        for i in range(count):
            run_id=f"synthetic-{user}-{i}"; completed=base+timedelta(days=i)
            runs.append(CompletedRun(completed_run_id=run_id,user_id=f"synthetic_{user}",route_id="synthetic_route",completed_at=completed,actual_distance_km=5,actual_duration_min=30,predicted_difficulty=generic))
            feedback.append(DifficultyFeedback(feedback_id=f"feedback-{run_id}",user_id=f"synthetic_{user}",route_id="synthetic_route",completed_run_id=run_id,difficulty=actual,created_at=completed+timedelta(minutes=5)))
    (output_dir/"completed_runs.json").write_text(json.dumps([x.model_dump(mode="json") for x in runs], indent=2))
    (output_dir/"difficulty_feedback.json").write_text(json.dumps([x.model_dump(mode="json") for x in feedback], indent=2))
    (output_dir/"README.txt").write_text("SYNTHETIC EVALUATION DATA ONLY. Never copy into runtime/personalization or accounts storage.\n")
    return runs, feedback

if __name__ == "__main__":
    from outdoorwise.config import Settings
    generate(Path(Settings.from_env().data_root)/"runtime/evaluation/synthetic")
