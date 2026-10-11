from datetime import datetime, timezone
from statistics import median
from .models import CompletedRun, DifficultyFeedback, UserRunningProfile

class PersonalizedDifficultyPredictor:
    model_version = "personalized-difficulty-v1"
    def predict(self, route_id, route_distance_km, generic_difficulty, runs: list[CompletedRun], feedback: list[DifficultyFeedback], profile: UserRunningProfile):
        feedback_by_run = {f.completed_run_id: f for f in feedback}
        pairs = [r.actual_distance_km for r in []]  # keeps inputs explicit; no favourites/profile inference
        residuals = [feedback_by_run[r.completed_run_id].difficulty - r.predicted_difficulty for r in runs if r.completed_run_id in feedback_by_run and r.predicted_difficulty is not None]
        residuals = residuals[-10:]; n = len(residuals); shrinkage = n / (n + 3) if n else 0
        historical_bias = median(residuals) if residuals else 0; bias_adjustment = shrinkage * historical_bias
        distance_adjustment = 0
        if profile.comfortable_distance_km and profile.comfortable_distance_km > 0:
            ratio = max(-.5, min(1.0, (route_distance_km - profile.comfortable_distance_km) / profile.comfortable_distance_km))
            distance_adjustment = .5 * ratio * shrinkage
        total = max(1, min(5, generic_difficulty + bias_adjustment + distance_adjustment))
        confidence = "none" if not n else "low" if n <= 2 else "medium" if n <= 5 else "high"
        reasons = [f"Adjusted {total-generic_difficulty:+.2f} from the generic estimate using {n} rated prediction pair(s)."] if n else ["Not enough history yet — currently using the generic estimate."]
        if distance_adjustment: reasons.append(f"Comfortable-distance adjustment: {distance_adjustment:+.2f}.")
        return {"route_id": route_id, "generic_predicted_difficulty": round(generic_difficulty,2), "personalized_predicted_difficulty": round(total,2), "total_adjustment": round(total-generic_difficulty,2), "historical_bias": round(historical_bias,2), "bias_adjustment": round(bias_adjustment,2), "distance_adjustment": round(distance_adjustment,2), "usable_history_count": n, "shrinkage_weight": round(shrinkage,3), "confidence": confidence, "reasons": reasons, "model_version": self.model_version, "generated_at": datetime.now(timezone.utc)}
