import csv, json, math, argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from outdoorwise.config import Settings
from outdoorwise.personalization.models import CompletedRun, DifficultyFeedback
from outdoorwise.personalization.profile import derive_running_profile
from outdoorwise.personalization.repository import PersonalizationRepository
from outdoorwise.personalization.difficulty import PersonalizedDifficultyPredictor

def _metrics(rows):
    if not rows: return {"mae": None, "rmse": None, "exact_rounded_accuracy": None, "within_one_accuracy": None, "mean_signed_error": None}
    errors=[r["prediction"]-r["actual"] for r in rows]
    return {"mae":sum(abs(x) for x in errors)/len(errors),"rmse":math.sqrt(sum(x*x for x in errors)/len(errors)),"exact_rounded_accuracy":sum(round(max(1,min(5,r["prediction"])))==r["actual"] for r in rows)/len(rows),"within_one_accuracy":sum(abs(x)<=1 for x in errors)/len(rows),"mean_signed_error":sum(errors)/len(errors)}

def evaluate(runs: list[CompletedRun], feedback: list[DifficultyFeedback]):
    feedback_by_run={f.completed_run_id:f for f in feedback}; grouped=defaultdict(list)
    for run in runs: grouped[run.user_id].append(run)
    raw=[]; skipped=defaultdict(int)
    for user_id, user_runs in grouped.items():
        ordered=sorted(user_runs,key=lambda r:r.completed_at)
        for index, run in enumerate(ordered):
            f=feedback_by_run.get(run.completed_run_id)
            if f is None: skipped["missing_feedback"]+=1; continue
            if run.predicted_difficulty is None: skipped["missing_generic_prediction"]+=1; continue
            if run.completed_at is None: skipped["invalid_completion_timestamp"]+=1; continue
            prior=[r for r in ordered[:index] if r.completed_at < run.completed_at]
            prior_ids={r.completed_run_id for r in prior}; prior_feedback=[x for x in feedback if x.user_id==user_id and x.completed_run_id in prior_ids]
            profile=derive_running_profile(user_id,prior,prior_feedback,[])
            replay=PersonalizedDifficultyPredictor().predict(run.route_id,run.actual_distance_km,run.predicted_difficulty,prior,prior_feedback,profile)
            raw.append({"user_id":user_id,"completed_run_id":run.completed_run_id,"completed_at":run.completed_at.isoformat(),"actual_difficulty":f.difficulty,"generic_prediction":run.predicted_difficulty,"saved_personalized_prediction":run.personalized_predicted_difficulty,"replayed_personalized_prediction":replay["personalized_predicted_difficulty"],"generic_absolute_error":abs(run.predicted_difficulty-f.difficulty),"personalized_absolute_error":abs(replay["personalized_predicted_difficulty"]-f.difficulty),"prior_history_count":replay["usable_history_count"]})
    generic=[{"prediction":r["generic_prediction"],"actual":r["actual_difficulty"]} for r in raw]; personal=[{"prediction":r["replayed_personalized_prediction"],"actual":r["actual_difficulty"]} for r in raw]
    gm,pm=_metrics(generic),_metrics(personal); users=defaultdict(list)
    for r in raw: users[r["user_id"]].append(r)
    buckets={"0 prior runs":lambda n:n==0,"1-2 prior runs":lambda n:1<=n<=2,"3-5 prior runs":lambda n:3<=n<=5,"6+ prior runs":lambda n:n>=6}
    curve=[]
    for name,match in buckets.items():
        rows=[r for r in raw if match(r["prior_history_count"])]
        g=_metrics([{"prediction":r["generic_prediction"],"actual":r["actual_difficulty"]} for r in rows]); p=_metrics([{"prediction":r["replayed_personalized_prediction"],"actual":r["actual_difficulty"]} for r in rows]); curve.append({"prior_history_group":name,"n":len(rows),"generic_mae":g["mae"],"personalised_mae":p["mae"],"improvement":None if g["mae"] is None or p["mae"] is None else g["mae"]-p["mae"]})
    per_user=[]
    for user_id,rows in sorted(users.items()):
        g=_metrics([{"prediction":r["generic_prediction"],"actual":r["actual_difficulty"]} for r in rows]); p=_metrics([{"prediction":r["replayed_personalized_prediction"],"actual":r["actual_difficulty"]} for r in rows]); per_user.append({"user_id":user_id,"n":len(rows),"generic_mae":g["mae"],"personalised_mae":p["mae"],"improvement":g["mae"]-p["mae"]})
    improvement=None if gm["mae"] is None or pm["mae"] is None else gm["mae"]-pm["mae"]
    return {"overall":{"observation_count":len(raw),"user_count":len(users),"generic":gm,"personalised":pm,"mae_absolute_improvement":improvement,"mae_percentage_improvement":None if improvement is None or not gm["mae"] else improvement/gm["mae"]},"learning_curve":curve,"per_user":per_user,"raw_predictions":raw,"skipped":{"count":sum(skipped.values()),"reasons":dict(skipped)}}

def write_outputs(result, output_dir):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/"personalization_evaluation.json").write_text(json.dumps(result,indent=2))
    for name,key in [("personalization_predictions.csv","raw_predictions"),("personalization_learning_curve.csv","learning_curve"),("personalization_per_user.csv","per_user")]:
        rows=result[key]
        with (output_dir/name).open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]) if rows else [])
            if rows: writer.writeheader(); writer.writerows(rows)
    from .plots import write_summary
    write_summary(result, output_dir / "personalization_summary.csv")

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--synthetic", action="store_true"); args=parser.parse_args()
    settings=Settings.from_env(); evaluation_dir=Path(settings.data_root)/"runtime/evaluation"
    if args.synthetic:
        from .synthetic_personalization import generate
        runs, feedback=generate(evaluation_dir/"synthetic")
    else:
        repo=PersonalizationRepository(settings.data_root); runs=[CompletedRun.model_validate(x) for x in repo._read("runs")]; feedback=[DifficultyFeedback.model_validate(x) for x in repo._read("feedback")]
    result=evaluate(runs,feedback); write_outputs(result,evaluation_dir)
    from .plots import make_plots
    make_plots(result,evaluation_dir/"figures")
    print(json.dumps(result["overall"],indent=2))
if __name__ == "__main__": main()
