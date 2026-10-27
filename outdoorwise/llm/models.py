
from pydantic import BaseModel, Field, ConfigDict


class RoutePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    prefer_green: bool = True
    prefer_quiet: bool = True
    avoid_steps: bool = True


class ParsedRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location: str | None = Field(default=None, max_length=200)

    target_distance_km: float = Field(
        default=5, ge=1, le=30
    )

    target_difficulty: int = Field(
        default=3, ge=1, le=5
    )

    preferences: RoutePreferences = Field(
        default_factory=RoutePreferences
    )
