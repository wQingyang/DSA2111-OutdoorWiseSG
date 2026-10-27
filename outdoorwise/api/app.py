"""FastAPI composition root for the catalog, dynamic routes and static frontend.

Application mode selects Tab 1 orchestration only. Tab 2 keeps the configured
current-environment repository; starting a live API never collects observations.
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from outdoorwise.accounts.repository import AccountRepository
from outdoorwise.accounts.router import (
    get_repository as get_account_repository,
    router as accounts_router,
)
from outdoorwise.api.forecast_ranking import router as forecast_ranking_router
from outdoorwise.api.recommendation_workflow import router as recommendation_workflow_router
from outdoorwise.api.time_selection import router as time_selection_router
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.models import Preferences, Route, Run
from outdoorwise.difficulty.router import router as difficulty_router
from outdoorwise.export.router import router as export_router
from outdoorwise.llm.router import router as llm_router
from outdoorwise.personalization.repository import PersonalizationRepository
from outdoorwise.personalization.router import (
    get_service,
    me_router as personalization_me_router,
    router as personalization_router,
)
from outdoorwise.personalization.service import PersonalizationService
from outdoorwise.routing.environment import DynamicRouteEnvironmentService
from outdoorwise.routing.ors_client import OpenRouteServiceClient
from outdoorwise.routing.repository import GeneratedRouteRepository
from outdoorwise.routing.router import router as routing_router
from outdoorwise.routing.service import DynamicRouteService


def create_app(settings: Settings | None = None):
    """Build request-scoped adapters around shared repositories and services.

    Tests provide settings pointing at temporary storage. Dependency overrides
    ensure authenticated routes use this application's account/user stores.
    """
    settings = settings or Settings.from_env()
    pipeline = build_pipeline(settings)

    @asynccontextmanager
    async def lifespan(app):
        if settings.data_mode == 'demo' and settings.app_mode == 'live':
            pipeline.refresh()
        yield

    app = FastAPI(title='OutdoorWise', version='0.2.0', lifespan=lifespan)
    app.state.app_mode = settings.app_mode
    app.state.pipeline = pipeline
    app.state.generated_route_repository = GeneratedRouteRepository(settings.data_root)
    app.state.dynamic_routes = DynamicRouteService(
        OpenRouteServiceClient(settings.routing_base_url, settings.routing_api_key),
        app.state.generated_route_repository,
    )
    app.state.dynamic_route_environment = DynamicRouteEnvironmentService(
        pipeline.repository, pipeline.config, pipeline.mode,
    )
    app.state.account_repository = AccountRepository(settings.data_root)
    app.state.personalization_service = PersonalizationService(
        PersonalizationRepository(settings.data_root)
    )
    app.dependency_overrides[get_service] = lambda: app.state.personalization_service
    app.dependency_overrides[get_account_repository] = lambda: app.state.account_repository

    app.include_router(personalization_router)
    app.include_router(personalization_me_router)
    app.include_router(accounts_router)
    app.include_router(difficulty_router)
    app.include_router(export_router)
    app.include_router(routing_router)
    app.include_router(time_selection_router)
    app.include_router(forecast_ranking_router)
    app.include_router(llm_router)
    app.include_router(recommendation_workflow_router)

    @app.get('/api/health')
    def health():
        return {
            'ok': True,
            'schema_version': '2.0',
            'data_mode': settings.data_mode,
            'app_mode': settings.app_mode,
            'dynamic_routing_configured': bool(settings.routing_api_key),
        }

    @app.get('/api/ready')
    def ready():
        """Check local storage access; source freshness is reported per route."""
        import os
        if not pipeline.repository.load_routes() or not os.access(pipeline.repository.runtime, os.W_OK):
            raise HTTPException(503, 'Catalog or runtime storage unavailable')
        return {'ready': True}

    @app.get('/api/routes', response_model=list[Route])
    def routes():
        return pipeline.repository.load_routes()

    @app.get('/api/routes/{route_id}/environment')
    def environment(route_id: str, as_of: str | None = None):
        from outdoorwise.contracts.environment import timestamp
        try:
            return pipeline.get_route_environment(route_id, timestamp(as_of) if as_of else None)
        except KeyError:
            raise HTTPException(404, 'Unknown route')
        except ValueError:
            raise HTTPException(422, 'as_of requires an ISO timestamp with timezone')

    @app.post('/api/refresh')
    def refresh():
        try:
            return pipeline.refresh()
        except (httpx.HTTPError, ValueError, KeyError) as e:
            # Failed collection retains observations; it never supplies demo values.
            raise HTTPException(
                503,
                'Collection failed. Existing observations are retained; check network/API availability.',
            ) from e

    @app.post('/api/recommendations', response_model=Run)
    def recommendations(preferences: Preferences):
        """Compatibility endpoint for observation-based catalog clients."""
        pipeline.ensure_demo_data_fresh()
        return pipeline.run(preferences)

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'frontend/index.html')

    @app.get('/login.html')
    def login_page():
        return FileResponse(ROOT / 'frontend/login.html')

    @app.get('/register.html')
    def register_page():
        return FileResponse(ROOT / 'frontend/register.html')

    @app.get('/profile.html')
    def profile_page():
        return FileResponse(ROOT / 'frontend/profile.html')

    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')
    return app


app = create_app()
