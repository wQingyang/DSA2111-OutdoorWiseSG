from .base import APICollector,observation
from outdoorwise.contracts.environment import CollectionBatch,Location
class WBGTCollector(APICollector):
    source="nea_wbgt"
    def parse(self,payload,fetched_at):
        rows=[];locations={}
        for record in payload["data"]["records"]:
            item=record["item"]
            if item["type"]!="observation" or item["isStationData"] is not True:
                raise ValueError("WBGT endpoint must supply official station observations")
            for r in item["readings"]:
                s=r["station"];sid=s["id"];raw=r.get("wbgt");category=r.get("heatStress")
                locations[sid]=Location(source=self.source,location_id=sid,name=s["name"],location_type="station",
                    lon=r["location"]["longitude"],lat=r["location"]["latitude"],metadata_updated_at=fetched_at)
                rows.append(observation(self.source,sid,"wbgt",float(raw) if raw not in {None,""} else None,
                    fetched_at,record["datetime"],record.get("updatedTimestamp"),raw_unit="degC",raw_value=float(raw) if raw not in {None,""} else None))
                rows.append(observation(self.source,sid,"heat_stress_level",None,fetched_at,record["datetime"],
                    record.get("updatedTimestamp"),category=category or None,raw_unit="category"))
        return CollectionBatch(source=self.source,fetched_at=fetched_at,locations=list(locations.values()),observations=rows)
