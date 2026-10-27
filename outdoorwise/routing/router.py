import httpx
from outdoorwise.contracts.models import Preferences, Recommendation
from outdoorwise.contracts.environment import utc_now
from outdoorwise.modules.risk import EnvironmentalRiskAssessor
from outdoorwise.modules.risk_ranking import RiskAwareRanking
from outdoorwise.personalization.ranking import rank_candidates
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
    current_user = None
    if request.cookies.get('outdoorwise_session'):
        current_user = current_user_from_request(request, request.app.state.account_repository)
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
    pipeline = request.app.state.pipeline
    as_of = utc_now()
    environments, generic_predictions, personal_predictions, risks = {}, {}, {}, {}
    candidates = []
    for route in result.candidates:
        environment = request.app.state.dynamic_route_environment.evaluate(route, as_of)
        generic = GenericDifficultyEstimator().predict(route, environment)
        environments[route.route_id] = environment
        generic_predictions[route.route_id] = generic
        risks[route.route_id] = EnvironmentalRiskAssessor(pipeline.config).assess([environment], as_of)[0]
        if current_user:
            personal_predictions[route.route_id] = request.app.state.personalization_service.get_personalized_difficulty(
                current_user.user_id, route, environment)
        score = 100 - route.distance_error_pct - 10 * abs(generic.predicted_difficulty - data.target_difficulty)
        candidates.append(Recommendation(route_id=route.route_id, score=score, access_distance_km=0,
            distance_difference_km=abs(route.distance_km - data.target_distance_km), reasons=[]))
    candidates.sort(key=lambda row: (-row.score, row.route_id))
    preferences = Preferences(target_distance_km=data.target_distance_km, target_difficulty=data.target_difficulty)
    ranked = RiskAwareRanking(pipeline.config.ranking).rank(candidates, list(risks.values()), result.candidates,
        preferences, {key: value.predicted_difficulty for key, value in generic_predictions.items()})
    blocked = [row for row in ranked if row.eligibility == 'blocked']
    ranked = [row for row in ranked if row.eligibility != 'blocked']
    shared_positions = {row.route_id: index for index, row in enumerate(ranked, 1)}
    if current_user:
        personal_order = rank_candidates(ranked, list(personal_predictions.values()), data.target_difficulty)
        by_id = {row.route_id: row for row in ranked}
        ranked = [by_id[row['route_id']] for row in personal_order]
    def assessment(row, rank):
        return GeneratedRouteAssessment(route_id=row.route_id, rank=rank, score=round(row.score, 2),
            environment=environments[row.route_id], generic_difficulty=generic_predictions[row.route_id],
            personalized_difficulty=personal_predictions.get(row.route_id), environmental_risk=risks[row.route_id],
            recommendation_score=row.recommendation_score, recommendation_components=row.recommendation_components,
            ranking_method=row.ranking_method, ranking_reasons=row.ranking_reasons,
            pipeline_rank=shared_positions.get(row.route_id))
    routes_by_id = {route.route_id: route for route in result.candidates}
    warnings = list(result.warnings)
    warnings.append('Observation-based shared risk policy; generated geometry requires on-site access checks.')
    if blocked: warnings.append('Explicit environmental policy excluded blocked candidates from recommendations.')
    if ranked and all(row.recommendation_score is None for row in ranked):
        warnings.append('Environmental suitability unknown: discovery order uses distance/difficulty only.')
    return result.model_copy(update={'candidates': [routes_by_id[row.route_id] for row in ranked],
        'assessments': [assessment(row, index) for index, row in enumerate(ranked, 1)],
        'blocked_assessments': [assessment(row, index) for index, row in enumerate(blocked, 1)],
        'excluded_route_ids': [row.route_id for row in blocked], 'warnings': warnings})



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
