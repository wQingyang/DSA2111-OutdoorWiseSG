"""Validated startup settings and source/risk configuration.

Application mode changes Tab 1's workflow; data mode selects the operational
repository source kind. Freshness thresholds and polling cadence are separate.
"""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from .contracts.risk import RiskConfig, RankingConfig

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    """Immutable process settings; credentials stay server-side and out of CSV."""
    data_root: Path = ROOT / 'data'
    environment_config: Path = ROOT / 'config/environment.toml'
    data_mode: str = 'live'
    app_mode: str = 'live'
    data_api_key: str = ''
    routing_base_url: str = 'https://api.heigit.org/openrouteservice'
    routing_api_key: str = ''

    def __post_init__(self):
        if self.app_mode not in {'live', 'historical'}:
            raise ValueError('OUTDOORWISE_APP_MODE must be live or historical')

    @classmethod
    def from_env(cls):
        s = cls(
            data_root=Path(os.getenv('OUTDOORWISE_DATA_ROOT', str(ROOT / 'data'))),
            environment_config=Path(os.getenv('OUTDOORWISE_ENV_CONFIG', str(ROOT / 'config/environment.toml'))),
            data_mode=os.getenv('OUTDOORWISE_DATA_MODE', 'live'),
            app_mode=os.getenv('OUTDOORWISE_APP_MODE', 'live'),
            data_api_key=os.getenv('DATA_GOV_API_KEY', ''),
            routing_base_url=os.getenv('OUTDOORWISE_ROUTING_BASE_URL', 'https://api.heigit.org/openrouteservice'),
            routing_api_key=os.getenv('ORS_API_KEY', ''),
        )
        if s.data_mode not in {'demo', 'live'}:
            raise ValueError('Data mode must be demo or live')
        return s


class SourceConfig(BaseModel):
    """One official source's cadence, observation age limit and metric contract."""
    model_config = ConfigDict(extra='forbid')
    url: str
    interval_seconds: int = Field(gt=0)
    stale_after_seconds: int = Field(gt=0)
    metrics: list[str]


class CollectionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0, le=5)
    retry_backoff_seconds: float = Field(ge=0)
    max_retry_delay_seconds: float = Field(ge=0, le=60)
    request_spacing_seconds: float = Field(ge=0, le=10)


class MatchingConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    station_max_distance_km: float = Field(gt=0)
    representative_method: str
    route_regions: dict[str, str]


class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    collection: CollectionConfig
    matching: MatchingConfig
    sources: dict[str, SourceConfig]
    risk: RiskConfig = Field(default_factory=RiskConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)


def load_environment_config(path: Path) -> EnvironmentConfig:
    """Reject source/metric mismatches before collection or risk assessment."""
    from .contracts.environment import METRIC_SPECS
    with path.open('rb') as f:
        result = EnvironmentConfig.model_validate(tomllib.load(f))
    if result.matching.representative_method != 'start_point_v1':
        raise ValueError('Only start_point_v1 is implemented; add sampling strategy before switching')
    expected = {source for _, _, source in METRIC_SPECS.values()}
    if set(result.sources) != expected:
        raise ValueError('Configured sources must match registered collectors')
    for source, cfg in result.sources.items():
        metrics = {m for m, (_, _, s) in METRIC_SPECS.items() if s == source}
        if set(cfg.metrics) != metrics or len(cfg.metrics) != len(metrics):
            raise ValueError('Source metric list disagrees with contract')
    for metric, (_, _, source) in METRIC_SPECS.items():
        if source not in result.sources or metric not in result.sources[source].metrics:
            raise ValueError(f'Missing config for {metric}')
    return result
