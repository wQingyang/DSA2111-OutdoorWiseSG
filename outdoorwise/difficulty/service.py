from datetime import datetime, timezone
from .models import GenericDifficultyPrediction
WEIGHTS = {"distance": 1.5, "wbgt": 1.0, "temperature": .5, "humidity": .35, "rainfall": .35, "heat_stress": 1.0}
def label(score): return "Very easy" if score <= 1.8 else "Easy" if score <= 2.6 else "Moderate" if score <= 3.4 else "Hard" if score <= 4.2 else "Very hard"
class GenericDifficultyEstimator:
    model_version = "generic-rule-v1"
    def predict(self, route, environment):
        values={m.metric:m for m in environment.metrics}; components={"distance":min(WEIGHTS["distance"],route.distance_km/8*WEIGHTS["distance"])}; reasons=[f"Distance contributes +{components['distance']:.2f} for {route.distance_km:.2f} km."]; available=1
        def numeric(name): return values[name].value if name in values and values[name].value is not None else None
        wbgt = numeric("wbgt")
        heat = values.get("heat_stress_level")
        if wbgt is not None:
            components["wbgt"] = max(0, min(WEIGHTS["wbgt"], (wbgt - 26) / 8 * WEIGHTS["wbgt"])); available += 1
            reasons.append(f"WBGT contributes +{components['wbgt']:.2f}; other correlated heat signals are excluded.")
        elif heat and heat.category_value:
            components["heat_stress"] = {"Low": 0, "Moderate": .5, "High": 1}[heat.category_value]; available += 1
            reasons.append(f"Official heat-stress category contributes +{components['heat_stress']:.2f}; temperature and humidity are excluded.")
        else:
            heat = None
        for name,threshold,scale,weight,text in [("air_temperature",28,8,.5,"Temperature"),("relative_humidity",60,40,.35,"Humidity"),("rainfall",0,10,.35,"Rainfall")]:
            if name != "rainfall" and (wbgt is not None or heat is not None): continue
            value=numeric(name)
            if value is not None:
                available+=1; components["temperature" if name=="air_temperature" else name]=max(0,min(weight,(value-threshold)/scale*weight)) if name!="rainfall" else min(weight,value/scale*weight); reasons.append(f"{text} contributes +{components['temperature' if name=='air_temperature' else name]:.2f}.")
        score=max(1,min(5,1+sum(components.values())))
        return GenericDifficultyPrediction(route_id=route.route_id,predicted_difficulty=round(score,2),difficulty_label=label(score),components={k:round(v,2) for k,v in components.items()},reasons=reasons,available_feature_count=available,data_quality="full" if available>=4 else "partial" if available>1 else "distance_only",generated_at=datetime.now(timezone.utc),model_version=self.model_version)
