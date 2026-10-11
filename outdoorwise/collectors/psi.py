from .base import APICollector,region_locations,observation
from outdoorwise.contracts.environment import CollectionBatch
class PSICollector(APICollector):
    source="nea_psi"
    def parse(self,payload,fetched_at):
        data=payload["data"];locations=region_locations(data,self.source,fetched_at);rows=[]
        for item in data["items"]:
            for field,metric,unit in [("psi_twenty_four_hourly","psi","index"),("pm10_twenty_four_hourly","pm10","ug/m3")]:
                # Never use pm10_sub_index as concentration; missing field is a parser failure.
                values=item["readings"][field]
                for loc in locations:
                    rows.append(observation(self.source,loc.location_id,metric,values.get(loc.location_id),fetched_at,
                        item["timestamp"],item.get("updatedTimestamp"),raw_unit=unit,raw_value=values.get(loc.location_id)))
        return CollectionBatch(source=self.source,fetched_at=fetched_at,locations=locations,observations=rows)
