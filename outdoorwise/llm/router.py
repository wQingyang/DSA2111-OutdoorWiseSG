
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from outdoorwise.routing.models import RouteGenerationResponse

from .models import ParsedRouteRequest
from .parser import parse_route_request
from .explainer import explain_routes


router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
)


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ExplainRequest(BaseModel):
    route_response: RouteGenerationResponse
    target_distance_km: float = Field(ge=1, le=30)
    target_difficulty: int = Field(ge=1, le=5)


class ExplainResponse(BaseModel):
    explanation: str


def check_api_key():
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="LLM API is not configured.",
        )


def handle_llm_error(exc: Exception):
    # Avoid exposing private provider or request details.
    if isinstance(exc, (ValueError, ValidationError)):
        raise HTTPException(
            status_code=502,
            detail="LLM returned an invalid response.",
        ) from exc

    raise HTTPException(
        status_code=502,
        detail="LLM provider request failed.",
    ) from exc


@router.post(
    "/parse",
    response_model=ParsedRouteRequest,
)
def parse_endpoint(request: ParseRequest):
    check_api_key()

    try:
        return parse_route_request(request.text)
    except Exception as exc:
        handle_llm_error(exc)


@router.post(
    "/explain",
    response_model=ExplainResponse,
)
def explain_endpoint(request: ExplainRequest):
    check_api_key()

    try:
        explanation = explain_routes(
            request.route_response.model_dump(
                mode="json"
            ),
            request.target_distance_km,
            request.target_difficulty,
        )

        return ExplainResponse(
            explanation=explanation
        )

    except Exception as exc:
        handle_llm_error(exc)
