import os
import tomllib
from pydantic import BaseModel, ConfigDict, Field
from dataclasses import dataclass
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
@dataclass(frozen=True)
class Settings:
    data_root: Path = ROOT / "data"
    environment_config: Path = ROOT / "config/environment.toml"
    data_mode: str = "live"
    agent_mode: str = "demo"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: str = ""
    data_api_key: str = ""
    @classmethod
    def from_env(cls):
        s = cls(data_root=Path(os.getenv("OUTDOORWISE_DATA_ROOT", str(ROOT / "data"))),
                environment_config=Path(os.getenv("OUTDOORWISE_ENV_CONFIG", str(ROOT / "config/environment.toml"))),
                data_mode=os.getenv("OUTDOORWISE_DATA_MODE", "live"),
                agent_mode=os.getenv("OUTDOORWISE_AGENT_MODE", "demo"),
                llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
                llm_model=os.getenv("LLM_MODEL", ""), llm_api_key=os.getenv("LLM_API_KEY", ""),
                data_api_key=os.getenv("DATA_GOV_API_KEY", ""))
        if s.data_mode not in {"demo", "live"} or s.agent_mode not in {"demo", "llm"}:
            raise ValueError("Modes must be demo/live for data, demo/llm for agent")
        if s.agent_mode == "llm" and not (s.llm_model and s.llm_api_key):
            raise ValueError("LLM mode requires LLM_MODEL and LLM_API_KEY")
        return s

class SourceConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    url: str
    interval_seconds: int = Field(gt=0)
    stale_after_seconds: int = Field(gt=0)
    metrics: list[str]
class CollectionConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    timeout_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0, le=5)
    retry_backoff_seconds: float = Field(ge=0)
    max_retry_delay_seconds: float = Field(ge=0, le=60)
    request_spacing_seconds: float = Field(ge=0, le=10)
class MatchingConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    station_max_distance_km: float = Field(gt=0)
    representative_method: str
    route_regions: dict[str,str]
class EnvironmentConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    collection: CollectionConfig
    matching: MatchingConfig
    sources: dict[str,SourceConfig]
def load_environment_config(path: Path) -> EnvironmentConfig:
    from .contracts.environment import METRIC_SPECS
    with path.open("rb") as f: result=EnvironmentConfig.model_validate(tomllib.load(f))
    if result.matching.representative_method!="start_point_v1":
        raise ValueError("Only start_point_v1 is implemented; add sampling strategy before switching")
    expected={source for _,_,source in METRIC_SPECS.values()}
    if set(result.sources)!=expected:raise ValueError("Configured sources must match registered collectors")
    for source,cfg in result.sources.items():
        metrics={m for m,(_,_,s) in METRIC_SPECS.items() if s==source}
        if set(cfg.metrics)!=metrics or len(cfg.metrics)!=len(metrics):raise ValueError("Source metric list disagrees with contract")
    for metric,(_,_,source) in METRIC_SPECS.items():
        if source not in result.sources or metric not in result.sources[source].metrics:
            raise ValueError(f"Missing config for {metric}")
    return result
