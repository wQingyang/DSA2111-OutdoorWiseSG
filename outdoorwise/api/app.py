from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from outdoorwise.config import Settings,ROOT
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.contracts.models import Preferences,Run,ChatRequest,ChatResponse,Route
from outdoorwise.agent.service import AgentService
def create_app(settings: Settings | None=None):
    settings=settings or Settings.from_env(); pipeline=build_pipeline(settings)
    @asynccontextmanager
    async def lifespan(app):
        if settings.data_mode=='demo': pipeline.refresh()
        yield
    app=FastAPI(title='OutdoorWise',version='0.2.0',lifespan=lifespan)
    app.state.pipeline=pipeline
    @app.get('/api/health')
    def health(): return {'ok':True,'schema_version':'2.0','data_mode':settings.data_mode,'agent_mode':settings.agent_mode}
    @app.get('/api/routes',response_model=list[Route])
    def routes(): return pipeline.repository.load_routes()
    @app.get('/api/routes/{route_id}/environment')
    def environment(route_id:str,as_of: str | None=None):
        from outdoorwise.contracts.environment import timestamp
        try:return pipeline.get_route_environment(route_id,timestamp(as_of) if as_of else None)
        except KeyError:raise HTTPException(404,'Unknown route')
        except ValueError:raise HTTPException(422,'as_of requires an ISO timestamp with timezone')
    @app.post('/api/refresh')
    def refresh():
        try: return pipeline.refresh()
        except (httpx.HTTPError,ValueError,KeyError) as e:
            # Existing observations remain intact; never silently replace live data with demo.
            raise HTTPException(503,'Collection failed. Existing observations are retained; check network/API availability.') from e
    @app.post('/api/recommendations',response_model=Run)
    def recommendations(preferences: Preferences): return pipeline.run(preferences)
    @app.post('/api/chat',response_model=ChatResponse)
    def chat(request: ChatRequest):
        try: return AgentService(pipeline,settings).chat(request)
        except (httpx.HTTPError,KeyError,ValueError) as e:
            raise HTTPException(502,'Agent provider failed; verify server configuration and provider availability.') from e
    @app.get('/')
    def index(): return FileResponse(ROOT/'frontend/index.html')
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
    return app
app=create_app()
