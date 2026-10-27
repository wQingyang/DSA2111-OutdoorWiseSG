"""Dispatch unified Tab 1 by server mode while preserving compatibility and Tab 2."""
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from outdoorwise.contracts.models import Preferences
from outdoorwise.personalization.ranking import rank_candidates
from .forecast_ranking import RankingRequest, optional_user, rank_historical
from .time_selection import REPLAY_TIME

router = APIRouter(prefix='/api/route-recommendations', tags=['Route recommendation workflow'])


class RecommendationRequest(Preferences):
    start_delay_min: Literal[0, 30, 60] = 0


@router.post('')
def recommend(data: RecommendationRequest, request: Request, response: Response, user=Depends(optional_user)):
    response.headers['Cache-Control'] = 'no-store'
    pipeline = request.app.state.pipeline
    service = request.app.state.personalization_service
    app_mode = request.app.state.app_mode
    if app_mode == 'historical':
        try:
            result = rank_historical(RankingRequest(**data.model_dump()), pipeline, user, service,
                                     conservative_coverage=True)
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            raise HTTPException(503, 'Required historical snapshot or prediction dependency is unavailable.') from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        result['missing_inputs'] = {row['route_id']: [name for name, item in row['risk_components'].items() if item['score'] is None] for row in result['recommendations']}
        result['forecast_coverage'] = 'incomplete_native_targets_only'
        result.update(app_mode=app_mode, assessment_type='historical_observation' if data.start_delay_min == 0 else 'forecast_based',
                      assessment_reference_time=REPLAY_TIME, environmental_source='snapshot_20261015',
                      requested_departure_offset_min=data.start_delay_min, run_duration_min=data.duration_min)
        return result
    if data.start_delay_min != 0:
        raise HTTPException(422, 'Live Mode supports departure Now (0 minutes) only.')
    pipeline.ensure_demo_data_fresh()
    run = pipeline.run(Preferences(**data.model_dump(exclude={'start_delay_min'})))
    result = run.model_dump(mode='json')
    personal = []
    if user is not None:
        env = {row.route_id: row for row in run.environment}
        routes = {row.route_id: row for row in run.routes}
        predictions = [service.get_personalized_difficulty(user.user_id, routes[row.route_id], env[row.route_id])
                       for row in run.recommendations]
        personal = rank_candidates(run.recommendations, predictions, data.target_difficulty)
        order = {row['route_id']: index for index, row in enumerate(personal)}
        result['recommendations'].sort(key=lambda row: order[row['route_id']])
    result['missing_inputs'] = {env.route_id: [metric.metric for metric in env.metrics if metric.state != 'fresh'] for env in run.environment}
    result['forecast_coverage'] = 'not_applicable_current_observations_only'
    result.update(app_mode=app_mode, assessment_type='observed',
                  assessment_reference_time=result['generated_at'], environmental_source=f'{pipeline.mode}_repository',
                  requested_departure_offset_min=0, run_duration_min=data.duration_min,
                  run_start=result['generated_at'],
                  run_end=(run.generated_at + timedelta(minutes=data.duration_min)).isoformat(),
                  personalized=user is not None, personalized_recommendations=personal)
    return result
