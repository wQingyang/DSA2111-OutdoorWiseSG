
from pydantic import BaseModel, Field, ConfigDict


class RoutePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefer_green: bool = True
    prefer_quiet: bool = True
    avoid_steps: bool = True


class ParsedRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str | None = None

    target_distance_km: float = Field(
        default=5, ge=1, le=30
    )

    target_difficulty: int = Field(
        default=3, ge=1, le=5
    )

    preferences: RoutePreferences = Field(
        default_factory=RoutePreferences
    )
