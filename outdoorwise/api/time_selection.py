"""Compatibility APIs for native historical forecasts and supplementary live baselines."""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator


router = APIRouter(
    prefix="/api/time-selection",
    tags=["Time selection"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Fixed historical replay time, not current weather.
REPLAY_TIME = "2026-10-15T19:15:00+08:00"


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(min_length=1, max_length=100)
    start_delay_min: Literal[0, 30, 60, 120] = 0
    duration_min: int = Field(
        default=30,
        ge=1,
        le=180,
        strict=True,
    )

    @model_validator(mode="after")
    def check_window(self):
        if self.start_delay_min + self.duration_min > 180:
            raise ValueError(
                "Start delay plus duration must not exceed 180 minutes."
            )
        return self


@lru_cache(maxsize=48)
def historical_forecast(route_id, start_delay_min, duration_min):
    # Existing experiment files import sibling modules directly.
    prediction_dir = str(PROJECT_ROOT / "prediction")

    if prediction_dir not in sys.path:
        sys.path.insert(0, prediction_dir)

    from predict_route_risk import predict, air

    return predict(
        route_id,
        air.parse_timestamp(REPLAY_TIME),
        start_delay_min,
        duration_min,
    )


@router.post("/forecast")
def forecast(request: ForecastRequest):
    try:
        return historical_forecast(
            request.route_id,
            request.start_delay_min,
            request.duration_min,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Historical dataset or model file is missing.",
        ) from exc

    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Prediction modules or dependencies are missing.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

@router.post("/live-forecast")
def live_forecast(data: ForecastRequest, request: Request, response: Response):
    """Live persistence evidence, separate from the fixed historical replay."""
    from outdoorwise.services.live_prediction import LivePredictionService
    response.headers['Cache-Control'] = 'no-store'
    pipeline = request.app.state.pipeline
    try:
        return LivePredictionService(pipeline.repository, pipeline.config, pipeline.mode).predict(
            data.route_id, data.start_delay_min, data.duration_min)
    except KeyError as exc:
        raise HTTPException(404, 'Unknown route') from exc
