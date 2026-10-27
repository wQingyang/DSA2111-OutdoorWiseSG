from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from outdoorwise.contracts.core import Contract, Coordinate
from outdoorwise.contracts.models import LineString
from outdoorwise.contracts.environment import RouteEnvironment, EnvironmentRisk
from outdoorwise.difficulty.models import GenericDifficultyPrediction


class RouteGenerationPreferences(Contract):
    prefer_green: bool = True
    prefer_quiet: bool = True
    avoid_steps: bool = True


class RouteGenerationRequest(Contract):
    start: Coordinate
    target_distance_km: float = Field(ge=1, le=30)
    candidate_count: int = Field(default=3, ge=1, le=5)
    distance_tolerance_pct: float = Field(default=15, ge=5, le=30)
    target_difficulty: int = Field(default=3, ge=1, le=5)
    preferences: RouteGenerationPreferences = Field(default_factory=RouteGenerationPreferences)


class GeneratedRoute(Contract):
    route_id: str
    name: str
    kind: Literal["loop"] = "loop"
    distance_km: float = Field(gt=0)
    target_distance_km: float = Field(gt=0)
    distance_error_pct: float = Field(ge=0)
    status: Literal["generated_validated"] = "generated_validated"
    geometry: LineString
    attribution: str = "openrouteservice.org, OpenStreetMap contributors"
    provider: str = "openrouteservice"
    seed: int
    created_at: AwareDatetime
    expires_at: AwareDatetime
    warnings: list[str] = Field(default_factory=list)


class RouteGenerationResponse(Contract):
    candidates: list[GeneratedRoute]
    rejected_count: int
    rejection_reasons: dict[str, int] = Field(default_factory=dict)
    assessments: list["GeneratedRouteAssessment"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    excluded_route_ids: list[str] = Field(default_factory=list)
    blocked_assessments: list["GeneratedRouteAssessment"] = Field(default_factory=list)


class GeneratedRouteAssessment(Contract):
    route_id: str
    rank: int = Field(ge=1)
    score: float
    environment: RouteEnvironment
    environmental_risk: EnvironmentRisk | None = None
    recommendation_score: float | None = None
    recommendation_components: dict[str, float] = Field(default_factory=dict)
    ranking_method: str = 'legacy_non_environmental'
    ranking_reasons: list[str] = Field(default_factory=list)
    pipeline_rank: int | None = None
    generic_difficulty: GenericDifficultyPrediction
    personalized_difficulty: dict | None = None

