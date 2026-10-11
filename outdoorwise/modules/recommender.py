"""Owner 5: transparent baseline, replace with your scoring implementation."""
from outdoorwise.contracts.models import Recommendation, Coordinate
from outdoorwise.contracts.geo import distance_km
class BaselineRecommender:
    def rank(self, routes, conditions, predictions, preferences):
        predictions={p.route_id:p for p in predictions}; conditions={c.route_id:c for c in conditions}; out=[]
        for route in routes:
            access=None
            if preferences.location:
                lon,lat=route.geometry.coordinates[0]
                access=distance_km(preferences.location,Coordinate(lon=lon,lat=lat))
                if preferences.max_access_distance_km and access>preferences.max_access_distance_km: continue
            diff=abs(route.distance_km-preferences.target_distance_km)
            p=predictions[route.route_id]; c=conditions[route.route_id]
            score=100-10*diff-(2*access if access is not None else 0)
            reasons=[f'Route length {route.distance_km:.3f} km; target difference {diff:.3f} km.']
            if access is not None: reasons.append(f'Straight-line access distance {access:.2f} km; not travel distance/time.')
            if p.rain_probability is not None:
                score-=50*p.rain_probability
                reasons.append(f'{"SIMULATED " if p.is_mock else ""}{p.horizon_min}-minute rain probability {p.rain_probability:.0%}.')
            else: reasons.append('Rain forecast unavailable; ranking uses distance only.')
            reasons.append(f'Observation quality: {c.quality}. Route status: {route.status}.')
            out.append(Recommendation(route_id=route.route_id,score=round(score,2),access_distance_km=round(access,3) if access is not None else None,
                distance_difference_km=round(diff,3),reasons=reasons))
        return sorted(out,key=lambda r:(-r.score,r.route_id))
