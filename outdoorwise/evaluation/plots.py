import csv, math
from pathlib import Path

def make_plots(evaluation_json, output_dir):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data=evaluation_json if isinstance(evaluation_json,dict) else __import__("json").loads(Path(evaluation_json).read_text())
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    overall=data["overall"]; g=overall["generic"]["mae"] or 0; p=overall["personalised"]["mae"] or 0
    fig,ax=plt.subplots(figsize=(6,4)); ax.bar(["Generic","Personalised"],[g,p],color=["#617567","#24684c"]); ax.set_ylabel("MAE"); ax.set_title("Generic vs personalised MAE"); fig.tight_layout(); fig.savefig(output_dir/"mae_comparison.png",dpi=160); plt.close(fig)
    curve=data["learning_curve"]; labels=[x["prior_history_group"] for x in curve]; fig,ax=plt.subplots(figsize=(7,4)); ax.plot(labels,[x["generic_mae"] or math.nan for x in curve],marker="o",label="Generic"); ax.plot(labels,[x["personalised_mae"] or math.nan for x in curve],marker="o",label="Personalised"); ax.set_ylabel("MAE"); ax.set_title("Learning over time"); ax.legend(); fig.tight_layout(); fig.savefig(output_dir/"learning_curve.png",dpi=160); plt.close(fig)
    raw=data["raw_predictions"]; fig,ax=plt.subplots(figsize=(6,5)); actual=[x["actual_difficulty"] for x in raw]; ax.scatter(actual,[x["generic_prediction"] for x in raw],label="Generic",alpha=.8); ax.scatter(actual,[x["replayed_personalized_prediction"] for x in raw],label="Personalised",alpha=.8); ax.plot([1,5],[1,5],"k--",label="Perfect"); ax.set(xlabel="Actual difficulty",ylabel="Predicted difficulty",title="Predicted vs actual difficulty",xlim=(1,5),ylim=(1,5)); ax.legend(); fig.tight_layout(); fig.savefig(output_dir/"predicted_vs_actual.png",dpi=160); plt.close(fig)
    users=data["per_user"]; fig,ax=plt.subplots(figsize=(7,4)); names=[x["user_id"] for x in users]; ax.bar(names,[x["generic_mae"] or 0 for x in users],label="Generic"); ax.bar(names,[x["personalised_mae"] or 0 for x in users],bottom=[x["generic_mae"] or 0 for x in users],label="Personalised"); ax.set_ylabel("MAE"); ax.set_title("Per-user prediction error"); ax.tick_params(axis="x",rotation=30); ax.legend(); fig.tight_layout(); fig.savefig(output_dir/"per_user_improvement.png",dpi=160); plt.close(fig)

def write_summary(data, path):
    o=data["overall"]; row={"observation_count":o["observation_count"],"user_count":o["user_count"],"generic_mae":o["generic"]["mae"],"personalised_mae":o["personalised"]["mae"],"absolute_improvement":o["mae_absolute_improvement"],"percentage_improvement":o["mae_percentage_improvement"],"generic_rmse":o["generic"]["rmse"],"personalised_rmse":o["personalised"]["rmse"],"generic_exact_accuracy":o["generic"]["exact_rounded_accuracy"],"personalised_exact_accuracy":o["personalised"]["exact_rounded_accuracy"],"generic_within_one_accuracy":o["generic"]["within_one_accuracy"],"personalised_within_one_accuracy":o["personalised"]["within_one_accuracy"]}
    with Path(path).open("w",newline="") as f: writer=csv.DictWriter(f,fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
