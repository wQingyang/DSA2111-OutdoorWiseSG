from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .service import RouteExportService

router = APIRouter(prefix="/api/routes", tags=["export"])


@router.get("/{route_id}/export.gpx")
def export_gpx(route_id:str,request:Request):
    pipeline = request.app.state.pipeline
    route = next((item for item in pipeline.repository.load_routes() if item.route_id == route_id), None)
    if route is None:
        raise HTTPException(404, "Unknown route")
    data = RouteExportService().render_gpx(route)
    date = datetime.now().date().isoformat()
    return Response(data, media_type="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="outdoorwise_{route.route_id}_{date}.gpx"'})
