from fastapi import APIRouter, Depends, HTTPException

from outdoorwise.config import Settings

from .models import (CompletedRun, CompletedRunCreate, DifficultyFeedback,
                     DifficultyFeedbackCreate, FavouriteRoute)
from .repository import PersonalizationRepository
from .service import PersonalizationService

router = APIRouter(prefix="/api/users/{user_id}", tags=["personalization"])


def get_service() -> PersonalizationService:
    return PersonalizationService(PersonalizationRepository(Settings.from_env().data_root))


@router.post("/runs", response_model=CompletedRun, status_code=201)
def create_run(user_id: str, data: CompletedRunCreate, service: PersonalizationService = Depends(get_service)):
    return service.create_completed_run(user_id, data)


@router.get("/runs", response_model=list[CompletedRun])
def list_runs(user_id: str, service: PersonalizationService = Depends(get_service)):
    return service.list_completed_runs(user_id)


@router.get("/runs/{completed_run_id}", response_model=CompletedRun)
def get_run(user_id: str, completed_run_id: str, service: PersonalizationService = Depends(get_service)):
    result = service.get_completed_run(user_id, completed_run_id)
    if result is None:
        raise HTTPException(404, "Completed run not found")
    return result


@router.put("/favourites/{route_id}", response_model=FavouriteRoute)
def add_favourite(user_id: str, route_id: str, service: PersonalizationService = Depends(get_service)):
    return service.add_favourite(user_id, route_id)


@router.delete("/favourites/{route_id}", status_code=204)
def delete_favourite(user_id: str, route_id: str, service: PersonalizationService = Depends(get_service)):
    if not service.remove_favourite(user_id, route_id):
        raise HTTPException(404, "Favourite route not found")


@router.get("/favourites", response_model=list[FavouriteRoute])
def list_favourites(user_id: str, service: PersonalizationService = Depends(get_service)):
    return service.list_favourites(user_id)


@router.post("/runs/{completed_run_id}/feedback", response_model=DifficultyFeedback, status_code=201)
def add_feedback(user_id: str, completed_run_id: str, data: DifficultyFeedbackCreate,
                 service: PersonalizationService = Depends(get_service)):
    run = service.get_completed_run(user_id, completed_run_id)
    if run is None:
        raise HTTPException(404, "Completed run not found")
    try:
        return service.add_feedback(user_id, run.route_id, completed_run_id, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/feedback", response_model=list[DifficultyFeedback])
def list_feedback(user_id: str, service: PersonalizationService = Depends(get_service)):
    return service.list_feedback(user_id)
