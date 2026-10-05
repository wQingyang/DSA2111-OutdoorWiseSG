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
class Observation(Contract):
    station_id: str
    location: Coordinate
    metric: Literal["rainfall"]
    value: float = Field(ge=0)
    unit: Literal["mm"] = "mm"
    observed_at: AwareDatetime
    collected_at: AwareDatetime
    source: Literal["demo_fixture", "data_gov_sg"]
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
class Preferences(Contract):
    target_distance_km: float = Field(default=4, gt=0, le=100)
    duration_min: int = Field(default=30, ge=1, le=60)
    horizon_min: Literal[30,60] = 30
    location: Coordinate | None = None
    max_access_distance_km: float | None = Field(default=None, gt=0)
class Recommendation(Contract):
    route_id: str
    score: float
    access_distance_km: float | None = None
    distance_difference_km: float
    reasons: list[str]
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
class ChatRequest(Contract):
    message: str = Field(min_length=1, max_length=2000)
    preferences: Preferences = Field(default_factory=Preferences)
class Trace(Contract):
    tool: str
    arguments: dict
    result: dict
class ChatResponse(Contract):
    message: str
    agent_mode: Literal["demo", "llm"]
    trace: list[Trace]
    recommended_route_ids: list[str]
    run: Run | None
