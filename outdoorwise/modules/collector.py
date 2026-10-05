"""Owner 2: replace/extend collection, keep Collector signature."""
from datetime import datetime, timezone
import httpx
from outdoorwise.contracts.models import Observation, Coordinate
API_URL="https://api-open.data.gov.sg/v2/real-time/api/rainfall"
class DemoCollector:
    def collect(self):
        now=datetime.now(timezone.utc)
        return [Observation(station_id=s,location=Coordinate(lon=x,lat=y),metric='rainfall',
          value=v,observed_at=now,collected_at=now,source='demo_fixture')
          for s,x,y,v in [('DEMO_SOUTH',103.855,1.287,0),('DEMO_NORTH',103.782,1.452,1.2)]]
def parse_rainfall(payload: dict, collected_at: datetime) -> list[Observation]:
    if payload.get('code') != 0: raise ValueError('Rainfall API returned a nonzero code')
    data=payload['data']; stations={s['id']:s for s in data['stations']}
    readings=data['readings']
    if not readings: raise ValueError('Rainfall API returned no readings')
    latest=max(readings,key=lambda r:datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')))
    out=[]
    for r in latest['data']:
        station=stations.get(r['stationId'])
        if station is None or r.get('value') is None: continue
        loc=station['location']
        out.append(Observation(station_id=r['stationId'], location=Coordinate(lon=loc['longitude'],lat=loc['latitude']),
         metric='rainfall',value=r['value'],observed_at=latest['timestamp'],
         collected_at=collected_at,source='data_gov_sg'))
    if not out: raise ValueError('Rainfall API returned no usable station values')
    return out
class LiveCollector:
    def __init__(self, api_key=''): self.api_key=api_key
    def collect(self):
        headers={'x-api-key':self.api_key} if self.api_key else {}
        with httpx.Client(timeout=20) as client:
            r=client.get(API_URL,headers=headers); r.raise_for_status()
            return parse_rainfall(r.json(),datetime.now(timezone.utc))
