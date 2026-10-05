"""Copy into your owned module and bind in bootstrap.py; never read CSV directly."""
from outdoorwise.contracts.ports import RouteEnvironmentReader
from outdoorwise.contracts.models import Conditions,Prediction
from outdoorwise.contracts.environment import EnvironmentRisk,RouteEnvironment
class YourPredictor:
    def __init__(self,environment:RouteEnvironmentReader):self.environment=environment
    def predict(self,conditions:list[Conditions],horizon_min:int)->list[Prediction]:
        features=[self.environment.get_route_environment(c.route_id) for c in conditions]
        # Return exactly one typed Prediction per route. Null if unavailable.
        # Future forecast output is persisted separately by the repository.
        raise NotImplementedError
class YourRiskAssessor:
    def assess(self,environments:list[RouteEnvironment])->list[EnvironmentRisk]:
        # Official heat stress is already present; do not pretend a missing score is zero.
        raise NotImplementedError
class YourRecommender:
    def __init__(self,environment:RouteEnvironmentReader):self.environment=environment
    def rank(self,routes,conditions,predictions,preferences):
        # Read typed environments, then return Recommendation objects.
        raise NotImplementedError
