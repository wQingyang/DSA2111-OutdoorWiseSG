"""Explicit synthetic values; never used on live collection failure."""
from outdoorwise.contracts.environment import CollectionBatch,Location,EnvironmentObservation,METRIC_SPECS,utc_now
class DemoEnvironmentCollector:
    def __init__(self,source):self.source=source
    def collect(self):
        now=utc_now();regional=self.source in {"nea_pm25","nea_psi"};locations=[];observations=[]
        for side,lon,lat in [("south",103.855,1.287),("north",103.782,1.452)]:
            sid=side if regional else "DEMO_"+side.upper()
            locations.append(Location(source=self.source,location_id=sid,name="Synthetic "+side,
                location_type="region" if regional else "station",lon=lon,lat=lat,metadata_updated_at=now,source_kind="demo"))
            for metric,(unit,window,source) in METRIC_SPECS.items():
                if source!=self.source:continue
                values={"rainfall":0 if side=="south" else 1.2,"wind_speed":2.5,"wind_direction":180,
                    "air_temperature":30,"relative_humidity":75,"pm25":12,"psi":35,"pm10":20,"wbgt":29}
                observations.append(EnvironmentObservation(source=source,location_id=sid,observed_at=now,fetched_at=now,
                    metric=metric,value=values.get(metric),category_value="Low" if metric=="heat_stress_level" else None,
                    unit=unit,aggregation_window=window,source_kind="demo"))
        return CollectionBatch(source=self.source,fetched_at=now,locations=locations,observations=observations),1
