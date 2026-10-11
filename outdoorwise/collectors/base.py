"""Shared HTTP transport only; every endpoint has an independent parser/collector."""
import time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import httpx
from outdoorwise.contracts.environment import CollectionBatch,EnvironmentObservation,METRIC_SPECS,Location,utc_now,timestamp
from outdoorwise.contracts.ports import CollectionFailure
class APICollector:
    source: str
    def __init__(self,source_config,collection_config,api_key=""):
        self.config=source_config;self.transport=collection_config;self.api_key=api_key
    def collect(self):
        attempts=0
        while True:
            attempts+=1
            try:
                with httpx.Client(timeout=self.transport.timeout_seconds) as client:
                    response=client.get(self.config.url,headers={"x-api-key":self.api_key} if self.api_key else {})
                    response.raise_for_status();payload=response.json()
                fetched_at=utc_now()
                if payload.get("code")!=0: raise ValueError("API returned nonzero code")
                batch=self.parse(payload,fetched_at)
                if not batch.observations: raise ValueError("No observations in source response")
                return batch,attempts
            except Exception as exc:
                retryable=isinstance(exc,(httpx.TransportError,httpx.HTTPStatusError))
                if isinstance(exc,httpx.HTTPStatusError):
                    retryable=exc.response.status_code==429 or exc.response.status_code>=500
                if not retryable or attempts>self.transport.max_retries:
                    # Do not emit API keys or full provider response in errors/logs.
                    status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
                    detail=f"HTTP {status}" if status else ("Parser/schema error: "+str(exc)[:200] if isinstance(exc,ValueError) else type(exc).__name__)
                    raise CollectionFailure(detail,attempts) from exc
                delay=self.transport.retry_backoff_seconds*2**(attempts-1)
                if isinstance(exc,httpx.HTTPStatusError):
                    header=exc.response.headers.get("Retry-After")
                    if header:
                        try:delay=max(delay,float(header))
                        except ValueError:
                            try:delay=max(delay,(parsedate_to_datetime(header)-utc_now()).total_seconds())
                            except (ValueError,TypeError):pass
                time.sleep(min(max(0,delay),self.transport.max_retry_delay_seconds))
    def parse(self,payload,fetched_at): raise NotImplementedError

def observation(source,location_id,metric,value,fetched_at,observed_at,source_updated_at=None,category=None,raw_unit=None,raw_value=None):
    unit,window,expected=METRIC_SPECS[metric]
    return EnvironmentObservation(source=source,location_id=location_id,metric=metric,value=value,
        category_value=category,unit=unit,aggregation_window=window,fetched_at=fetched_at,
        observed_at=timestamp(observed_at),source_updated_at=timestamp(source_updated_at) if source_updated_at else None,
        raw_unit=raw_unit,raw_value=raw_value)

def parse_station(payload,fetched_at,source,metric,expected_unit,expected_type,convert=lambda x:x):
    data=payload["data"]
    if data.get("readingUnit")!=expected_unit or data.get("readingType")!=expected_type:
        raise ValueError("Upstream reading unit/type changed; review parser before collecting")
    locations=[Location(source=source,location_id=s["id"],name=s["name"],location_type="station",
        lon=s["location"]["longitude"],lat=s["location"]["latitude"],metadata_updated_at=fetched_at) for s in data["stations"]]
    known={l.location_id for l in locations};rows=[]
    for group in data["readings"]:
        for r in group["data"]:
            if r["stationId"] not in known: raise ValueError("Unknown source station")
            raw=r.get("value")
            rows.append(observation(source,r["stationId"],metric,convert(float(raw)) if raw is not None else None,
                fetched_at,group["timestamp"],group.get("updatedTimestamp"),raw_unit=expected_unit,raw_value=raw))
    return CollectionBatch(source=source,fetched_at=fetched_at,locations=locations,observations=rows)

def region_locations(data,source,fetched_at):
    return [Location(source=source,location_id=r["name"],name=r["name"],location_type="region",
        lon=r["labelLocation"]["longitude"],lat=r["labelLocation"]["latitude"],metadata_updated_at=fetched_at)
        for r in data["regionMetadata"]]
