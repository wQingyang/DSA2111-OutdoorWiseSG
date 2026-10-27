from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from .core import Contract,Coordinate
from .environment import RouteEnvironment,EnvironmentRisk
class LineString(Contract):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)
class Route(Contract):
    route_id: str
    name: str
    kind: Literal["loop", "out_and_back", "point_to_point"]
    distance_km: float = Field(gt=0)
    status: str
    geometry: LineString
    attribution: str
class Conditions(Contract):
    route_id: str
    rainfall_mm: float | None = Field(default=None, ge=0)
    station_ids: list[str]
    max_station_distance_km: float | None = None
    observed_at: AwareDatetime | None = None
    source: Literal["demo_fixture", "data_gov_sg", "unavailable"]
    quality: Literal["demo", "fresh", "stale", "missing"]
class Prediction(Contract):
    route_id: str
    horizon_min: Literal[30,60]
    rain_probability: float | None = Field(default=None, ge=0, le=1)
    generated_at: AwareDatetime
    source: str
    is_mock: bool
    status: Literal["demo", "available", "unavailable"]
    prediction_status: Literal['forecast_available', 'forecast_unavailable'] = 'forecast_unavailable'
class Preferences(Contract):
    target_distance_km: float = Field(default=4, gt=0, le=100)
    duration_min: int = Field(default=30, ge=1, le=60)
    horizon_min: Literal[30,60] = 30
    location: Coordinate | None = None
    max_access_distance_km: float | None = Field(default=None, gt=0)
    target_difficulty: int = Field(default=3, ge=1, le=5)
class Recommendation(Contract):
    route_id: str
    score: float = Field(description='Legacy baseline score; not the final weighted score or a probability.')
    access_distance_km: float | None = None
    distance_difference_km: float
    reasons: list[str]
    relative_distance_difference: float = Field(default=0, ge=0)
    distance_match_warning: str | None = None
    risk_score: float | None = Field(default=None, ge=0, le=100)
    risk_level: str = 'unknown'
    risk_status: str = 'unavailable'
    risk_assessment_mode: str = 'current_observation'
    eligibility: Literal['eligible', 'caution', 'blocked', 'unknown'] = 'unknown'
    recommendation_score: float | None = Field(default=None, ge=0, le=100, description='Final weighted score when environmental assessment is complete; otherwise null.')
    recommendation_components: dict[str, float] = Field(default_factory=dict)
    ranking_method: str = 'legacy_non_environmental'
    ranking_reasons: list[str] = Field(default_factory=list)
    original_base_rank: int | None = Field(default=None, ge=1, description='Position in original baseline candidates before risk/personal reordering or blocking; gaps are allowed.')
    final_rank: int | None = Field(default=None, ge=1, description='One-based position in the returned final recommendation list.')
    risk_confidence: str = 'unknown'
class Run(Contract):
    schema_version: Literal["2.0"] = "2.0"
    run_id: str
    generated_at: AwareDatetime
    data_mode: Literal["demo", "live"]
    preferences: Preferences
    routes: list[Route]
    conditions: list[Conditions]
    predictions: list[Prediction]
    recommendations: list[Recommendation]
    warnings: list[str]
    environment: list["RouteEnvironment"] = Field(default_factory=list)
    risks: list["EnvironmentRisk"] = Field(default_factory=list)
