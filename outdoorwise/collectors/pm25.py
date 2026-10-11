from .base import APICollector,region_locations,observation
from outdoorwise.contracts.environment import CollectionBatch
class PM25Collector(APICollector):
    source="nea_pm25"
    def parse(self,payload,fetched_at):
        data=payload["data"];locations=region_locations(data,self.source,fetched_at);rows=[]
        for item in data["items"]:
            values=item["readings"]["pm25_one_hourly"]
            for loc in locations:
                rows.append(observation(self.source,loc.location_id,"pm25",values.get(loc.location_id),fetched_at,
                    item["timestamp"],item.get("updatedTimestamp"),raw_unit="ug/m3",raw_value=values.get(loc.location_id)))
        return CollectionBatch(source=self.source,fetched_at=fetched_at,locations=locations,observations=rows)
