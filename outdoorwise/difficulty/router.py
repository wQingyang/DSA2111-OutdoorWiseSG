from fastapi import APIRouter, HTTPException, Request
from .models import GenericDifficultyPrediction
from .service import GenericDifficultyEstimator
router=APIRouter(prefix="/api/routes",tags=["difficulty"])
@router.get("/{route_id}/difficulty",response_model=GenericDifficultyPrediction)
def route_difficulty(route_id:str,request:Request,as_of:str|None=None):
    from outdoorwise.contracts.environment import timestamp
    pipeline=request.app.state.pipeline; route=next((r for r in pipeline.repository.load_routes() if r.route_id==route_id),None)
    if route is None: raise HTTPException(404,"Unknown route")
    try: environment=pipeline.get_route_environment(route_id,timestamp(as_of) if as_of else None)
    except ValueError as exc: raise HTTPException(422,"as_of requires an ISO timestamp with timezone") from exc
    return GenericDifficultyEstimator().predict(route,environment)
