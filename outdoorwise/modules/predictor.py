"""Owner 4: trained model goes here. DEMO probabilities are fixtures, not forecasts."""
from datetime import datetime,timezone
from outdoorwise.contracts.models import Prediction
class DemoPredictor:
    def predict(self, conditions, horizon_min):
        values={'marina_bay':{30:.15,60:.30},'woodlands_waterfront':{30:.65,60:.75}}
        return [Prediction(route_id=c.route_id,horizon_min=horizon_min,
            rain_probability=values.get(c.route_id,{}).get(horizon_min),
            generated_at=datetime.now(timezone.utc),source='demo_fixture_v1',is_mock=True,status='demo') for c in conditions]
class UnavailablePredictor:
    def predict(self, conditions, horizon_min):
        return [Prediction(route_id=c.route_id,horizon_min=horizon_min,rain_probability=None,
            generated_at=datetime.now(timezone.utc),source='model_not_connected',is_mock=False,status='unavailable') for c in conditions]
