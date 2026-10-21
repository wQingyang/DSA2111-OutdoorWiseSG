"""Isolated historical forecast ranking; original recommendation APIs stay unchanged."""
import csv
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import model_validator

from outdoorwise.accounts.router import get_repository as account_repository
from outdoorwise.accounts.security import current_user_from_request
from outdoorwise.config import ROOT
from outdoorwise.contracts.environment import EnvironmentObservation, Location
from outdoorwise.contracts.models import Conditions, Preferences
from outdoorwise.modules.predictor import UnavailablePredictor
from outdoorwise.modules.recommender import BaselineRecommender
from outdoorwise.modules.risk import EnvironmentalRiskAssessor
from outdoorwise.modules.risk_ranking import RiskAwareRanking
from outdoorwise.personalization.profile import derive_running_profile
from outdoorwise.personalization.ranking import rank_candidates
from outdoorwise.services.route_environment import RouteEnvironmentService
from outdoorwise.storage.repository import typed
from .time_selection import REPLAY_TIME, historical_forecast

router = APIRouter(prefix="/api/experimental", tags=["Experimental forecast ranking"])


class RankingRequest(Preferences):
    start_delay_min: Literal[0, 30, 60, 120] = 0

    @model_validator(mode="after")
    def check_window(self):
        if self.start_delay_min + self.duration_min > 180:
            raise ValueError("Delay plus duration must not exceed 180 minutes.")
        return self


def optional_user(request: Request, repo=Depends(account_repository)):
    if not request.cookies.get("outdoorwise_session"):
        return None
    # An invalid session must not silently become another user's context.
    return current_user_from_request(request, repo)


@lru_cache(maxsize=2)
def load_snapshot(root, replay_time):
    """Read only; do not instantiate a runtime repository or write CSV files."""
    from outdoorwise.contracts.environment import timestamp
    as_of = timestamp(replay_time)
    folder = Path(root) / "data/datasets/snapshot_20261015"
    with (folder / "locations.csv").open(newline="", encoding="utf-8") as handle:
        locations = [typed(Location, row) for row in csv.DictReader(handle)
                     if row["source_kind"] == "live"]
    latest = {}
    for filename in ["weather_observations.csv", "heat_stress_observations.csv",
                     "air_quality_observations.csv"]:
        with (folder / filename).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["source_kind"] != "live":
                    continue
                observation = typed(EnvironmentObservation, row)
                available = max(t for t in [observation.observed_at,
                    observation.first_fetched_at or observation.fetched_at,
                    observation.source_updated_at] if t is not None)
                if available > as_of:
                    continue
                key = (observation.source, observation.location_id, observation.metric)
                previous = latest.get(key)
                if previous is None or (observation.observed_at, observation.revision) > (previous.observed_at, previous.revision):
                    latest[key] = observation
    return locations, list(latest.values())


def rank_historical(data, pipeline, user=None, personal_service=None):
    """Reuse candidate filtering and weighting at one consistent replay time."""
    from outdoorwise.contracts.environment import timestamp
    as_of = timestamp(REPLAY_TIME)
    preferences = Preferences.model_validate(data.model_dump(exclude={"start_delay_min"}))
    routes = pipeline.repository.load_routes()
    locations, observations = load_snapshot(str(ROOT), REPLAY_TIME)

    class ReadOnlySnapshot:
        def load_routes(self):
            return routes

        def environment_snapshot(self, source_kind, query_time):
            if source_kind != "live" or query_time != as_of:
                raise ValueError("This adapter supports only its fixed replay time.")
            return locations, observations, []

    environments = RouteEnvironmentService(ReadOnlySnapshot(), pipeline.config, "live").get_all(as_of)
    env_by_id = {item.route_id: item for item in environments}
    observation_risks = EnvironmentalRiskAssessor(pipeline.config).assess(environments, as_of)
    observation_by_id = {item.route_id: item for item in observation_risks}
    conditions = []
    for item in environments:
        rain = next(metric for metric in item.metrics if metric.metric == "rainfall")
        conditions.append(Conditions(route_id=item.route_id, rainfall_mm=rain.value,
            station_ids=[rain.location_id] if rain.location_id else [],
            max_station_distance_km=rain.station_distance_km, observed_at=rain.observed_at,
            source="data_gov_sg" if rain.value is not None else "unavailable", quality=rain.state))
    predictions = UnavailablePredictor().predict(conditions, preferences.horizon_min)
    candidates = BaselineRecommender().rank(routes, conditions, predictions, preferences)
    # Preserve access filtering and all existing observation-policy exclusions.
    excluded = [row.route_id for row in candidates if observation_by_id[row.route_id].eligibility == "blocked"]
    candidates = [row for row in candidates if row.route_id not in excluded]

    difficulties = {}
    personal_predictions = []
    runs, feedback, profile = [], [], None
    if user is not None:
        runs = [row for row in personal_service.list_completed_runs(user.user_id)
                if row.completed_at <= as_of]
        ids = {row.completed_run_id for row in runs}
        feedback = [row for row in personal_service.list_feedback(user.user_id)
                    if row.created_at <= as_of and row.completed_run_id in ids]
        profile = derive_running_profile(user.user_id, runs, feedback, [])
    for route in routes:
        generic = pipeline.difficulty.predict(route, env_by_id[route.route_id]).predicted_difficulty
        if user is None:
            difficulties[route.route_id] = generic
        else:
            personal = personal_service.adjust_difficulty(user.user_id, route, generic, runs, feedback, profile)
            personal_predictions.append(personal)
            difficulties[route.route_id] = personal["personalized_predicted_difficulty"]

    ranker = RiskAwareRanking(pipeline.config.ranking)
    # Shared historical ordering uses generic difficulty only. Personalization
    # is applied below through the same helper used by Current recommendations.
    generic_difficulties = {}
    for route in routes:
        generic_difficulties[route.route_id] = pipeline.difficulty.predict(
            route, env_by_id[route.route_id]).predicted_difficulty
    forecasts, proxy_risks = {}, []
    for candidate in candidates:
        forecast = historical_forecast(candidate.route_id, data.start_delay_min, data.duration_min)
        forecasts[candidate.route_id] = forecast
        if "forecast_risk" not in forecast:
            raise ValueError("The forecast API must import predict from predict_route_risk.")
        assessment = forecast["forecast_risk"]
        score = assessment["risk_score"]
        proxy_risks.append(SimpleNamespace(route_id=candidate.route_id, risk_score=score,
            risk_level="unknown", risk_status="complete" if score is not None else "incomplete",
            risk_assessment_mode="experimental_historical_forecast",
            risk_data_quality=SimpleNamespace(confidence="very_low"),
            eligibility="caution" if score is not None else "unknown"))
    shared_ranked = ranker.rank(candidates, proxy_risks, routes, preferences,
                                generic_difficulties, personalized=False)
    if user is not None:
        predictions_by_id = {item["route_id"]: item for item in personal_predictions}
        ranked = rank_candidates(shared_ranked,
                                 [predictions_by_id[row.route_id] for row in shared_ranked],
                                 data.target_difficulty)
    else:
        ranked = shared_ranked
    reference_positions = {row.route_id: row.final_rank for row in shared_ranked}
    # rank_candidates intentionally returns dictionaries. Normalize the
    # anonymous Pydantic results at this boundary so the response builder has
    # one representation and cannot mix attribute and mapping access.
    ranked = [row if isinstance(row, dict) else row.model_dump(mode="json") for row in ranked]
    route_by_id = {route.route_id: route for route in routes}
    rows = []
    for rec in ranked:
        route_id = rec["route_id"]
        route = route_by_id[route_id]
        personal = next((item for item in personal_predictions if item["route_id"] == route_id), None)
        pipeline_rank = rec.get("pipeline_rank", reference_positions[route_id])
        personalized_rank = rec.get("personalized_rank")
        generic = generic_difficulties[route_id]
        risk_score = rec.get("risk_score")
        recommendation_score = rec.get("recommendation_score")
        recommendation_components = rec.get("recommendation_components")
        access_distance = rec.get("access_distance_km")
        distance_warning = rec.get("distance_match_warning")
        eligibility = rec.get("eligibility")
        rows.append(dict(route_id=route_id, route_name=route.name, distance_km=route.distance_km,
            context="historical", pipeline_rank=pipeline_rank,
            personalized_rank=personalized_rank, final_rank=personalized_rank or pipeline_rank,
            reference_rank=reference_positions[route_id], recommendation_score=recommendation_score,
            recommendation_components=recommendation_components,
            forecast_risk_score=risk_score, risk_score=risk_score,
            assessment_status="experimental" if risk_score is not None else "incomplete",
            access_distance_km=access_distance, difficulty=(personal["personalized_predicted_difficulty"] if personal else generic),
            generic_difficulty=generic,
            personalized_difficulty=personal["personalized_predicted_difficulty"] if personal else None,
            target_difficulty=data.target_difficulty if user is not None else None,
            difficulty_mismatch=rec.get("difficulty_mismatch"),
            personal_confidence=personal["confidence"] if personal else None,
            eligibility=eligibility, distance_match_warning=distance_warning,
            risk_components=forecasts[route_id]["forecast_risk"]["components"],
            forecast_metrics=forecasts[route_id]["metrics"]))
    return dict(mode="experimental_historical_forecast_ranking", as_of=REPLAY_TIME,
        personalized=user is not None, preferences=data.model_dump(mode="json"),
        run_start=(as_of+timedelta(minutes=data.start_delay_min)).isoformat(),
        run_end=(as_of+timedelta(minutes=data.start_delay_min+data.duration_min)).isoformat(),
        routes=[route.model_dump(mode="json") for route in routes],
        recommendations=rows, excluded_route_ids=excluded,
        ranking_weights=pipeline.config.ranking.weights,
        warnings=["Historical experimental comparison, not current weather or a safety recommendation.",
                  "Reference ranks use observation risk at the SAME historical time, not the current homepage demo scores.",
                  "Rain and wind use persistence baselines; forecast skill is not established.",
                  "Missing-risk candidates use the existing fallback group, never a zero risk score.",
                  "Difficulty uses observations at the replay time; future difficulty is not predicted.",
                  "Personal history is user-scoped and filtered to the replay time; full edit/revision history is unavailable.",
                  "Snapshot station metadata is static; observation revision history is incomplete.",
                  "Original recommendation endpoints and persisted runs are unchanged."])


@router.post("/recommendations")
def recommendations(data: RankingRequest, request: Request, response: Response,
                    user=Depends(optional_user)):
    response.headers["Cache-Control"] = "no-store"
    try:
        return rank_historical(data, request.app.state.pipeline, user,
                               request.app.state.personalization_service)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise HTTPException(503, "Required snapshot, prediction modules or model files are missing.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
