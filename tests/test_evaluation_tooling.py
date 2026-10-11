import json
from outdoorwise.evaluation.synthetic_personalization import generate
from outdoorwise.evaluation.personalization import evaluate
from outdoorwise.evaluation.plots import make_plots, write_summary

def test_synthetic_generation_is_deterministic_and_isolated(tmp_path):
    a=tmp_path/"a"; b=tmp_path/"b"; runs_a,feedback_a=generate(a); runs_b,feedback_b=generate(b)
    assert [x.model_dump(mode="json") for x in runs_a] == [x.model_dump(mode="json") for x in runs_b]
    assert (a/"README.txt").read_text().startswith("SYNTHETIC")
    assert not (tmp_path/"runtime/personalization").exists()
    result=evaluate(runs_a,feedback_a); assert result["overall"]["observation_count"] == 20

def test_plotting_and_summary_handle_empty_and_valid_results(tmp_path):
    empty=evaluate([],[]); make_plots(empty,tmp_path/"empty_figures"); write_summary(empty,tmp_path/"empty.csv")
    assert (tmp_path/"empty_figures/mae_comparison.png").exists()
    runs,feedback=generate(tmp_path/"synthetic"); result=evaluate(runs,feedback); figures=tmp_path/"figures"; make_plots(result,figures); write_summary(result,tmp_path/"summary.csv")
    assert all((figures/name).exists() for name in ["mae_comparison.png","learning_curve.png","predicted_vs_actual.png","per_user_improvement.png"])
    assert "generic_mae" in (tmp_path/"summary.csv").read_text()
