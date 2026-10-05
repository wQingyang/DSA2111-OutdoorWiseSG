"""Version 2 environment contracts; units/windows are validated, not inferred by users."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field, AwareDatetime, model_validator
from .core import Contract, Coordinate
# Source update cadence is different from averaging window and observation resolution.
METRIC_SPECS = {
    "rainfall": ("mm", "PT5M", "nea_rainfall"),
    "wind_speed": ("m/s", "PT10M", "nea_wind_speed"),
    "wind_direction": ("degree", "PT10M", "nea_wind_direction"),
    "air_temperature": ("degC", "PT1M", "nea_air_temperature"),
    "relative_humidity": ("%", "PT1M", "nea_relative_humidity"),
    "pm25": ("ug/m3", "PT1H", "nea_pm25"),
    "psi": ("index", "PT24H", "nea_psi"),
    "pm10": ("ug/m3", "PT24H", "nea_psi"),
    "wbgt": ("degC", "PT15M", "nea_wbgt"),
    "heat_stress_level": ("category", "PT15M", "nea_wbgt"),
}
Metric = Literal["rainfall", "wind_speed", "wind_direction", "air_temperature", "relative_humidity", "pm25", "psi", "pm10", "wbgt", "heat_stress_level"]
class Location(Contract):
    source: str
    location_id: str = Field(min_length=1)
    name: str
    location_type: Literal["station", "region"]
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    source_kind: Literal["live", "demo"] = "live"
    metadata_updated_at: AwareDatetime
class EnvironmentObservation(Contract):
    source: str
    location_id: str = Field(min_length=1)
    observed_at: AwareDatetime
    source_updated_at: AwareDatetime | None = None
    fetched_at: AwareDatetime
    metric: Metric
    value: float | None = None
    category_value: str | None = None
    unit: str
    aggregation_window: str
    source_kind: Literal["live", "demo"] = "live"
    raw_value: float | None = None
    raw_unit: str | None = None
    revision: int = Field(default=1, ge=1)
    first_fetched_at: AwareDatetime | None = None
    @model_validator(mode="after")
    def validate_measurement(self):
        unit,window,source=METRIC_SPECS[self.metric]
        if (self.unit,self.aggregation_window,self.source)!=(unit,window,source):
            raise ValueError("Metric source/unit/window disagree with v2 contract")
        if self.metric=="heat_stress_level":
            if self.value is not None or self.category_value not in {None,"Low","Moderate","High"}:
                raise ValueError("Official heat stress is Low/Moderate/High or missing, never a numeric estimate")
        elif self.category_value is not None:
            raise ValueError("Numeric metrics cannot contain categories")
        if self.value is not None:
            if self.metric in {"rainfall","wind_speed","pm25","pm10","psi"} and self.value<0:
                raise ValueError("Negative concentration, rainfall, speed or index")
            if self.metric=="relative_humidity" and not 0<=self.value<=100: raise ValueError("Invalid humidity")
            if self.metric=="wind_direction" and not 0<=self.value<=360: raise ValueError("Invalid direction")
            if self.metric in {"air_temperature","wbgt"} and not -80<=self.value<=80: raise ValueError("Invalid temperature")
        return self
class CollectionBatch(Contract):
    source: str
    fetched_at: AwareDatetime
    locations: list[Location]
    observations: list[EnvironmentObservation]
    warnings: list[str] = Field(default_factory=list)
    @model_validator(mode="after")
    def validate_relations(self):
        keys={(l.source,l.location_id,l.source_kind) for l in self.locations}
        if any(o.source!=self.source or (o.source,o.location_id,o.source_kind) not in keys for o in self.observations):
            raise ValueError("Batch contains unknown locations or a different source")
        return self
class IngestionRun(Contract):
    run_id: str
    source: str
    source_kind: Literal["live","demo"]
    started_at: AwareDatetime
    finished_at: AwareDatetime
    status: Literal["success","failed","skipped"]
    attempts: int = 0
    received_records: int = 0
    inserted_records: int = 0
    revised_records: int = 0
    unchanged_records: int = 0
    error: str = ""
class RouteSourceMapping(Contract):
    route_id: str
    metric: Metric
    source: str
    location_id: str | None
    source_kind: Literal["live","demo"]
    match_method: str
    station_distance_km: float | None
    representative_lon: float
    representative_lat: float
    mapped_at: AwareDatetime
class RouteMetric(Contract):
    route_id: str
    metric: Metric
    value: float | None = None
    category_value: str | None = None
    unit: str
    aggregation_window: str
    source: str
    location_id: str | None = None
    location_name: str | None = None
    source_kind: Literal["live","demo"]
    delivery: Literal["live","cache","demo","unavailable"]
    state: Literal["fresh","stale","missing"]
    match_method: str
    station_distance_km: float | None = None
    observed_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    fetched_at: AwareDatetime | None = None
    as_of: AwareDatetime
    revision: int | None = None
    reason: str = ""
class RouteEnvironment(Contract):
    schema_version: Literal["2.0"] = "2.0"
    route_id: str
    as_of: AwareDatetime
    metrics: list[RouteMetric]
class EnvironmentRisk(Contract):
    route_id: str
    assessed_at: AwareDatetime
    status: Literal["unavailable","available","demo"] = "unavailable"
    source: str = "risk_module_not_connected"
    reasons: list[str] = Field(default_factory=list)
def utc_now(): return datetime.now(timezone.utc)
def timestamp(value):
    result=datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None: raise ValueError("Source timestamp must include timezone")
    return result.astimezone(timezone.utc)

