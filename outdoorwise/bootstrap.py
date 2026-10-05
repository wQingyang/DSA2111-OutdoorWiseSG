"""Only composition root: collaborators replace implementations here."""
from .config import Settings,load_environment_config
from .storage.repository import FileRepository
from .collectors.rainfall import RainfallCollector
from .collectors.wind_speed import WindSpeedCollector
from .collectors.wind_direction import WindDirectionCollector
from .collectors.temperature import TemperatureCollector
from .collectors.humidity import HumidityCollector
from .collectors.pm25 import PM25Collector
from .collectors.psi import PSICollector
from .collectors.wbgt import WBGTCollector
from .collectors.demo import DemoEnvironmentCollector
from .services.route_environment import RouteEnvironmentService
from .modules.predictor import DemoPredictor,UnavailablePredictor
from .modules.recommender import BaselineRecommender
from .modules.risk import UnavailableRiskAssessor
from .pipeline.runner import Pipeline
COLLECTORS=dict(zip(['nea_rainfall','nea_wind_speed','nea_wind_direction','nea_air_temperature','nea_relative_humidity','nea_pm25','nea_psi','nea_wbgt'],[RainfallCollector,WindSpeedCollector,WindDirectionCollector,TemperatureCollector,HumidityCollector,PM25Collector,PSICollector,WBGTCollector]))
def build_pipeline(settings:Settings):
    config=load_environment_config(settings.environment_config)
    repo=FileRepository(settings.data_root)
    collectors=[DemoEnvironmentCollector(s) if settings.data_mode=='demo' else COLLECTORS[s](c,config.collection,settings.data_api_key) for s,c in config.sources.items()]
    return Pipeline(repo,collectors,RouteEnvironmentService(repo,config,settings.data_mode),DemoPredictor() if settings.data_mode=='demo' else UnavailablePredictor(),BaselineRecommender(),UnavailableRiskAssessor(),settings.data_mode,config)
