import httpx
from fastapi import APIRouter, HTTPException, Request

from outdoorwise.export.service import RouteExportService
from outdoorwise.difficulty.service import GenericDifficultyEstimator
from outdoorwise.accounts.security import current_user_from_request
from fastapi.responses import Response

from .models import GeneratedRouteAssessment, RouteGenerationRequest, RouteGenerationResponse

router = APIRouter(prefix="/api/generated-routes", tags=["dynamic-routing"])


def _provider_error(response: httpx.Response) -> str | None:
    """Return only the provider's public validation message, never request headers."""
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        value = error.get("message")
    else:
        value = error
    if not isinstance(value, str):
        value = payload.get("message") if isinstance(payload, dict) else None
    return value[:300] if isinstance(value, str) and value.strip() else None


@router.post("", response_model=RouteGenerationResponse)
def generate_routes(data: RouteGenerationRequest, request: Request):
    try:
        result = request.app.state.dynamic_routes.generate(data)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            detail = "The routing API key was rejected. Copy the current HeiGIT Basic Key and restart the server."
        elif status == 429:
            detail = "The routing API quota or rate limit was reached. Check the openrouteservice dashboard and try again later."
        elif status == 400:
            reason = _provider_error(exc.response)
            detail = "The routing provider rejected this route request."
            if reason:
                detail += f" Provider message: {reason}"
            else:
                detail += " Try another start point or distance."
        else:
            detail = f"The routing provider returned HTTP {status}. Please try again."
        raise HTTPException(502, detail) from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Could not connect to the routing provider. Check the server network connection.") from exc
    if not result.candidates:
        reasons = "; ".join(f"{reason} ({count})" for reason, count in result.rejection_reasons.items())
        detail = "No route met the requested constraints."
        if reasons:
            detail += f" Rejection summary: {reasons}."
        detail += " Try a different start point, distance, or tolerance."
        raise HTTPException(422, detail)
    current_user = None
    try:
        current_user = current_user_from_request(request, request.app.state.account_repository)
    except HTTPException:
        pass
    evaluated = []
    for route in result.candidates:
        environment = request.app.state.dynamic_route_environment.evaluate(route)
        generic = GenericDifficultyEstimator().predict(route, environment)
        personalized = None
        predicted = generic.predicted_difficulty
        if current_user:
            personalized = request.app.state.personalization_service.get_personalized_difficulty(
                current_user.user_id, route, environment)
            predicted = personalized["personalized_predicted_difficulty"]
        score = 100 - route.distance_error_pct - 10 * abs(predicted - data.target_difficulty)
        evaluated.append((score, route, environment, generic, personalized))
    evaluated.sort(key=lambda item: (-item[0], item[1].distance_error_pct, item[1].route_id))
    assessments = [GeneratedRouteAssessment(route_id=route.route_id, rank=index, score=round(score, 2),
        environment=environment, generic_difficulty=generic, personalized_difficulty=personalized)
        for index, (score, route, environment, generic, personalized) in enumerate(evaluated, 1)]
    return result.model_copy(update={"candidates": [item[1] for item in evaluated], "assessments": assessments})


@router.get("/{route_id}")
def get_generated_route(route_id: str, request: Request):
    route = request.app.state.generated_route_repository.get(route_id)
    if route is None:
        raise HTTPException(404, "Generated route not found")
    return route


@router.get("/{route_id}/export.gpx")
def export_generated_route(route_id: str, request: Request):
    route = request.app.state.generated_route_repository.get(route_id)
    if route is None:
        raise HTTPException(404, "Generated route not found")
    return Response(RouteExportService().render_gpx(route), media_type="application/gpx+xml",
                    headers={"Content-Disposition": f'attachment; filename="outdoorwise_{route.route_id}.gpx"'})
