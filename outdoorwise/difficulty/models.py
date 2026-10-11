from datetime import datetime
from pydantic import BaseModel, Field
class GenericDifficultyPrediction(BaseModel):
    route_id: str
    predicted_difficulty: float = Field(ge=1, le=5)
    difficulty_label: str
    components: dict[str, float]
    reasons: list[str]
    available_feature_count: int
    data_quality: str
    generated_at: datetime
    model_version: str
