from fastapi import APIRouter, Depends, HTTPException, Request

from outdoorwise.config import Settings
from outdoorwise.accounts.models import UserPublic
from outdoorwise.accounts.router import get_current_user
from outdoorwise.contracts.models import Preferences

from .models import (CompletedRun, CompletedRunCreate, DifficultyFeedback,
                     DifficultyFeedbackCreate, FavouriteRoute, UserRunningProfile, PersonalizedRecommendationRequest)
from .ranking import rank_candidates
from .repository import PersonalizationRepository
from .service import PersonalizationService

router = APIRouter(prefix="/api/users/{user_id}", tags=["personalization"])
me_router = APIRouter(prefix="/api/me", tags=["personalization"])


def owner(user_id: str, current: UserPublic = Depends(get_current_user)):
    if user_id != current.user_id:
        raise HTTPException(403, "Cannot access another user's personalization data")
    return current


def get_service() -> PersonalizationService:
    return PersonalizationService(PersonalizationRepository(Settings.from_env().data_root))


@router.post("/runs", response_model=CompletedRun, status_code=201)
def create_run(user_id: str, data: CompletedRunCreate, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    return service.create_completed_run(user_id, data)


@router.get("/runs", response_model=list[CompletedRun])
def list_runs(user_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    return service.list_completed_runs(user_id)


@router.get("/runs/{completed_run_id}", response_model=CompletedRun)
def get_run(user_id: str, completed_run_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    result = service.get_completed_run(user_id, completed_run_id)
    if result is None:
        raise HTTPException(404, "Completed run not found")
    return result


@router.put("/favourites/{route_id}", response_model=FavouriteRoute)
def add_favourite(user_id: str, route_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    return service.add_favourite(user_id, route_id)


@router.delete("/favourites/{route_id}", status_code=204)
def delete_favourite(user_id: str, route_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    if not service.remove_favourite(user_id, route_id):
        raise HTTPException(404, "Favourite route not found")


@router.get("/favourites", response_model=list[FavouriteRoute])
def list_favourites(user_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    return service.list_favourites(user_id)


@router.post("/runs/{completed_run_id}/feedback", response_model=DifficultyFeedback, status_code=201)
def add_feedback(user_id: str, completed_run_id: str, data: DifficultyFeedbackCreate,
                 service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    run = service.get_completed_run(user_id, completed_run_id)
    if run is None:
        raise HTTPException(404, "Completed run not found")
    try:
        return service.add_feedback(user_id, run.route_id, completed_run_id, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/feedback", response_model=list[DifficultyFeedback])
def list_feedback(user_id: str, service: PersonalizationService = Depends(get_service), _=Depends(owner)):
    return service.list_feedback(user_id)


@me_router.get("/running-profile", response_model=UserRunningProfile)
def running_profile(current: UserPublic = Depends(get_current_user), service: PersonalizationService = Depends(get_service)):
    return service.get_running_profile(current.user_id)

@me_router.get("/routes/{route_id}/personalized-difficulty")
def personalized_difficulty(route_id: str, request: Request, current: UserPublic = Depends(get_current_user), service: PersonalizationService = Depends(get_service)):
    pipeline = request.app.state.pipeline
    route = next((r for r in pipeline.repository.load_routes() if r.route_id == route_id), None)
    if route is None: raise HTTPException(404, "Unknown route")
    return service.get_personalized_difficulty(current.user_id, route, pipeline.get_route_environment(route_id))

@me_router.post("/recommendations")
def personalized_recommendations(data: PersonalizedRecommendationRequest, request: Request, current: UserPublic = Depends(get_current_user), service: PersonalizationService = Depends(get_service)):
    pipeline=request.app.state.pipeline
    pipeline.ensure_demo_data_fresh()
    run=pipeline.run(Preferences.model_validate(data.model_dump()))
    by_id={e.route_id:e for e in run.environment}
    route_by_id={route.route_id:route for route in run.routes}
    predictions=[
        service.get_personalized_difficulty(current.user_id, route_by_id[rec.route_id], by_id[rec.route_id])
        for rec in run.recommendations
    ]
    ranked=rank_candidates(run.recommendations,predictions,data.target_difficulty)
    return {"run":run,"target_difficulty":data.target_difficulty,"recommendations":ranked}
