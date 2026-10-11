from pydantic import BaseModel, Field

class PersonalizedRankingRequest(BaseModel):
    target_difficulty: int = Field(ge=1, le=5)

def rank_candidates(recommendations, predictions, target_difficulty):
    if not recommendations: return []
    prediction_map={p["route_id"]:p for p in predictions}; output=[]
    for base_rank, rec in enumerate(recommendations, 1):
        personal=prediction_map[rec.route_id]; mismatch=abs(personal["personalized_predicted_difficulty"]-target_difficulty)
        score = -mismatch
        explanation = "Not enough personal history yet; ranking currently relies mostly on the generic difficulty estimate." if personal["confidence"] == "none" else (f"Ranked higher because your predicted difficulty is {personal['personalized_predicted_difficulty']:.1f}/5, close to your requested target of {target_difficulty}/5." if mismatch <= 1 else f"Ranked lower because this route is predicted to feel {personal['personalized_predicted_difficulty']:.1f}/5, above your requested target of {target_difficulty}/5.")
        output.append({"route_id":rec.route_id,"original_base_rank":base_rank,"personalized_rank":0,"base_recommendation_score":rec.score,"generic_difficulty":personal["generic_predicted_difficulty"],"personalized_difficulty":personal["personalized_predicted_difficulty"],"target_difficulty":target_difficulty,"difficulty_mismatch":round(mismatch,3),"personalized_score":round(score,4),"explanation":explanation,"confidence":personal["confidence"]})
    output.sort(key=lambda x:(x["difficulty_mismatch"],x["original_base_rank"]))
    for rank,item in enumerate(output,1): item["personalized_rank"]=rank
    return output
