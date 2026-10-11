from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from outdoorwise.contracts.models import Preferences


class CompletedRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(min_length=1)
    completed_at: AwareDatetime
    actual_distance_km: float = Field(gt=0)
    actual_duration_min: float = Field(gt=0)
    predicted_difficulty: float | None = Field(default=None, ge=1, le=5)
    personalized_predicted_difficulty: float | None = Field(default=None, ge=1, le=5)

class PersonalizedRecommendationRequest(Preferences):
    target_difficulty: int = Field(ge=1, le=5)


class CompletedRun(CompletedRunCreate):
    completed_run_id: str
    user_id: str
    average_pace_min_per_km: float | None = None

    @model_validator(mode="after")
    def calculate_pace(self):
        if self.average_pace_min_per_km is None:
            self.average_pace_min_per_km = self.actual_duration_min / self.actual_distance_km
        return self


class FavouriteRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    route_id: str
    created_at: AwareDatetime


DIFFICULTY_TAGS = {
    "too_hot", "too_hilly", "too_long", "too_many_stairs",
    "too_much_traffic", "insufficient_greenery",
}


class DifficultyFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    difficulty: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    comment: str | None = None

    @model_validator(mode="after")
    def validate_tags(self):
        invalid = set(self.tags) - DIFFICULTY_TAGS
        if invalid:
            raise ValueError(f"Unknown difficulty tags: {', '.join(sorted(invalid))}")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("Difficulty tags must be unique")
        return self


class DifficultyFeedback(DifficultyFeedbackCreate):
    feedback_id: str
    user_id: str
    route_id: str
    completed_run_id: str
    created_at: AwareDatetime


class UserRunningProfile(BaseModel):
    user_id: str
    completed_run_count: int
    feedback_count: int
    favourite_count: int
    total_distance_km: float | None = None
    mean_distance_km: float | None = None
    median_distance_km: float | None = None
    recent_mean_distance_km: float | None = None
    typical_distance_min_km: float | None = None
    typical_distance_max_km: float | None = None
    comfortable_distance_km: float | None = None
    mean_pace_min_per_km: float | None = None
    median_pace_min_per_km: float | None = None
    mean_perceived_difficulty: float | None = None
    median_perceived_difficulty: float | None = None
    recent_difficulty_trend: str | None = None
    usable_run_count: int
    profile_confidence: str
