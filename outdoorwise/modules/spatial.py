"""Owner 3: baseline samples route vertices; no invented fine-scale weather."""
from datetime import datetime, timezone
from outdoorwise.contracts.models import Coordinate, Conditions
from outdoorwise.contracts.geo import distance_km
class NearestStationMatcher:
    def match(self, routes, observations):
        latest={}
        for o in observations:
            if o.station_id not in latest or o.observed_at>latest[o.station_id].observed_at:
                latest[o.station_id]=o
        stations=list(latest.values()); now=datetime.now(timezone.utc); out=[]
        for route in routes:
            selected={}; distances=[]
            for lon,lat in route.geometry.coordinates:
                if not stations: break
                pos=Coordinate(lon=lon,lat=lat)
                o=min(stations,key=lambda o:distance_km(pos,o.location))
                d=distance_km(pos,o.location)
                if d<=10: selected[o.station_id]=o; distances.append(d)
            obs=list(selected.values())
            if not obs:
                out.append(Conditions(route_id=route.route_id,station_ids=[],source='unavailable',quality='missing')); continue
            age=max((now-o.observed_at).total_seconds() for o in obs)
            source=obs[0].source
            quality='stale' if age>900 or age < -60 else ('demo' if source=='demo_fixture' else 'fresh')
            out.append(Conditions(route_id=route.route_id, rainfall_mm=max(o.value for o in obs),
                station_ids=sorted(selected),max_station_distance_km=round(max(distances),3),
                observed_at=min(o.observed_at for o in obs),source=source,quality=quality))
        return out
