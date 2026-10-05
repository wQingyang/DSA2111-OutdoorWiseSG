"""Only this service matches sources to routes. Repository is injected by its port."""
from datetime import datetime
from outdoorwise.contracts.models import Coordinate
from outdoorwise.contracts.geo import distance_km
from outdoorwise.contracts.environment import (METRIC_SPECS,RouteMetric,RouteEnvironment,RouteSourceMapping,utc_now)
class StartPointStrategy:
    def representative(self,route):
        lon,lat=route.geometry.coordinates[0];return Coordinate(lon=lon,lat=lat)
    # Extension seam: replace with evenly-spaced GeoJSON sampling + per-segment aggregation.
class RouteEnvironmentService:
    def __init__(self,repository,config,source_kind,geometry_strategy=None):
        self.repository=repository;self.config=config;self.source_kind=source_kind
        self.geometry_strategy=geometry_strategy or StartPointStrategy()
    def _evaluate(self,as_of):
        if as_of.tzinfo is None:raise ValueError('as_of must be timezone-aware')
        routes=self.repository.load_routes();locations,observations,logs=self.repository.environment_snapshot(self.source_kind,as_of)
        latest={}
        for o in observations:
            k=(o.source,o.location_id,o.metric)
            if k not in latest or (o.observed_at,o.revision)>(latest[k].observed_at,latest[k].revision):latest[k]=o
        last_ingestion={}
        for log in logs:
            if log.status=='skipped':continue
            if log.source not in last_ingestion or log.finished_at>last_ingestion[log.source].finished_at:last_ingestion[log.source]=log
        out=[];mappings=[]
        for route in routes:
            point=self.geometry_strategy.representative(route);metrics=[]
            for metric,(unit,window,source) in METRIC_SPECS.items():
                regional=metric in {'pm25','psi','pm10'};selected=None;distance=None;reason=''
                if regional:
                    region=self.config.matching.route_regions.get(route.route_id)
                    method='configured_source_region_v1'
                    selected=next((l for l in locations if l.source==source and l.location_id==region and l.location_type=='region'),None)
                    if not region:reason='No curated regional assignment for this route'
                else:
                    method='nearest_available_station_start_point_v1'
                    candidates=[l for l in locations if l.source==source and l.location_type=='station'
                        and (source,l.location_id,metric) in latest
                        and (latest[(source,l.location_id,metric)].value is not None or latest[(source,l.location_id,metric)].category_value is not None)]
                    # Prefer fresh available stations, then use nearest stale source with explicit stale flag.
                    fresh=[l for l in candidates if (as_of-latest[(source,l.location_id,metric)].observed_at).total_seconds()<=self.config.sources[source].stale_after_seconds]
                    candidates=fresh or candidates
                    if candidates:
                        selected=min(candidates,key=lambda l:distance_km(point,Coordinate(lon=l.lon,lat=l.lat)))
                        distance=distance_km(point,Coordinate(lon=selected.lon,lat=selected.lat))
                        if distance>self.config.matching.station_max_distance_km:
                            reason='Nearest available station exceeds configured distance limit';selected=None
                observation=latest.get((source,selected.location_id,metric)) if selected else None
                state='missing';delivery='unavailable'
                if observation and (observation.value is not None or observation.category_value is not None):
                    age=(as_of-observation.observed_at).total_seconds()
                    state='fresh' if 0<=age<=self.config.sources[source].stale_after_seconds else 'stale'
                    failed=source in last_ingestion and last_ingestion[source].status=='failed'
                    delivery='demo' if self.source_kind=='demo' else ('cache' if failed or (as_of-observation.fetched_at).total_seconds()>self.config.sources[source].interval_seconds else 'live')
                    if failed:reason='Latest collection failed; retained source data shown'
                    elif state=='stale':reason='Observation exceeds freshness threshold'
                if state=='missing':reason=reason or 'No usable observation available as of requested time'
                m=RouteMetric(route_id=route.route_id,metric=metric,value=observation.value if observation else None,
                    category_value=observation.category_value if observation else None,unit=unit,aggregation_window=window,
                    source=source,location_id=selected.location_id if selected else None,location_name=selected.name if selected else None,
                    source_kind=self.source_kind,delivery=delivery,state=state,match_method=method,
                    station_distance_km=round(distance,3) if distance is not None else None,
                    observed_at=observation.observed_at if observation else None,source_updated_at=observation.source_updated_at if observation else None,
                    fetched_at=observation.fetched_at if observation else None,as_of=as_of,revision=observation.revision if observation else None,reason=reason)
                metrics.append(m)
                mappings.append(RouteSourceMapping(route_id=route.route_id,metric=metric,source=source,location_id=m.location_id,
                    source_kind=self.source_kind,match_method=method,station_distance_km=m.station_distance_km,
                    representative_lon=point.lon,representative_lat=point.lat,mapped_at=as_of))
            out.append(RouteEnvironment(route_id=route.route_id,as_of=as_of,metrics=metrics))
        return out,mappings
    def get_route_environment(self,route_id:str,as_of:datetime|None=None):
        envs,_=self._evaluate(as_of or utc_now())
        result=next((e for e in envs if e.route_id==route_id),None)
        if result is None:raise KeyError('Unknown route_id')
        return result
    def get_all(self,as_of:datetime|None=None):return self._evaluate(as_of or utc_now())[0]
    def refresh_latest(self):
        environments,mappings=self._evaluate(utc_now());self.repository.save_route_environment(environments,mappings);return environments
