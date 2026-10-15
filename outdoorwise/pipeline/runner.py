from datetime import datetime,timezone
from uuid import uuid4
import time
from outdoorwise.contracts.models import Preferences,Run,Conditions,Prediction,Recommendation
from outdoorwise.contracts.environment import CollectionBatch,IngestionRun,EnvironmentRisk,utc_now
from outdoorwise.contracts.ports import CollectionFailure,EnvironmentRepository,EnvironmentCollector,RouteEnvironmentReader
class Pipeline:
    def __init__(self,repository:EnvironmentRepository,collectors:list[EnvironmentCollector],environment_service,predictor,recommender,risk,mode,config,risk_ranking=None,difficulty=None):
        self.repository=repository;self.collectors=collectors;self.environment_service=environment_service
        self.predictor=predictor;self.recommender=recommender;self.risk=risk;self.mode=mode;self.config=config
        self.risk_ranking=risk_ranking;self.difficulty=difficulty
    def get_route_environment(self,route_id,as_of=None):
        return self.environment_service.get_route_environment(route_id,as_of)
    def refresh(self,due_only=False,should_stop=None):
        logs=[]
        for index,collector in enumerate(self.collectors):
            if should_stop and should_stop():break
            source=collector.source;start=utc_now()
            if due_only and not self.repository.source_due(source,self.mode,self.config.sources[source].interval_seconds,start):
                continue
            if index and self.mode=='live':time.sleep(self.config.collection.request_spacing_seconds)
            try:
                batch,attempts=collector.collect();batch=CollectionBatch.model_validate(batch)
                if batch.source!=source or any(o.source_kind!=self.mode for o in batch.observations):raise ValueError('Collector mode/source mismatch')
            except (CollectionFailure,ValueError,KeyError) as exc:
                log=IngestionRun(run_id=uuid4().hex,source=source,source_kind=self.mode,started_at=start,finished_at=utc_now(),status='failed',attempts=getattr(exc,'attempts',1),error=str(exc)[:250])
                self.repository.record_failure(log);logs.append(log);continue
            log=IngestionRun(run_id=uuid4().hex,source=source,source_kind=self.mode,started_at=start,finished_at=utc_now(),status='success',attempts=attempts)
            logs.append(self.repository.ingest(batch,log))
        environments=self.environment_service.refresh_latest()
        return {'status':'partial' if any(l.status=='failed' for l in logs) else 'success','sources':[l.model_dump(mode='json') for l in logs],'routes':len(environments),'metrics':sum(len(e.metrics) for e in environments)}
    def run(self, preferences: Preferences, difficulty_provider=None):
        routes=self.repository.load_routes()
        environments=self.environment_service.refresh_latest()
        conditions=[]
        for e in environments:
            m=next(m for m in e.metrics if m.metric=='rainfall')
            conditions.append(Conditions(route_id=e.route_id,rainfall_mm=m.value,station_ids=[m.location_id] if m.location_id else [],max_station_distance_km=m.station_distance_km,observed_at=m.observed_at,source=('demo_fixture' if self.mode=='demo' else 'data_gov_sg') if m.value is not None else 'unavailable',quality='demo' if self.mode=='demo' and m.value is not None else m.state))
        predictions=[Prediction.model_validate(x) for x in self.predictor.predict(conditions,preferences.horizon_min)]
        for prediction in predictions:
            prediction.prediction_status='forecast_available' if prediction.status=='available' and not prediction.is_mock and prediction.rain_probability is not None else 'forecast_unavailable'
        risks=[EnvironmentRisk.model_validate(x) for x in self.risk.assess(environments)]
        ids={r.route_id for r in routes}
        for items in [conditions,predictions,risks]:
            if len(items)!=len(ids) or {x.route_id for x in items}!=ids:
                raise ValueError('Module must return exactly one result for every route')
        if any(p.horizon_min!=preferences.horizon_min for p in predictions): raise ValueError('Prediction horizon mismatch')
        if self.mode=='live' and any(p.is_mock for p in predictions): raise ValueError('Live pipeline cannot consume demo predictions')
        if self.mode=='live':
            quality={c.route_id:c.quality for c in conditions}
            if any(p.status=='available' and quality[p.route_id] in {'stale','missing'} for p in predictions):
                raise ValueError('Available forecasts require fresh observations')
        recommendations=[Recommendation.model_validate(x) for x in self.recommender.rank(routes,conditions,predictions,preferences)]
        if len({x.route_id for x in recommendations})!=len(recommendations) or any(x.route_id not in ids for x in recommendations):
            raise ValueError('Invalid recommendation IDs')
        if self.risk_ranking:
            if difficulty_provider:
                difficulties=difficulty_provider(routes,environments)
            else:
                environment_by_id={e.route_id:e for e in environments}
                difficulties={r.route_id:self.difficulty.predict(r,environment_by_id[r.route_id]).predicted_difficulty for r in routes}
            recommendations=self.risk_ranking.rank(recommendations,risks,routes,preferences,difficulties,personalized=difficulty_provider is not None)
        blocked={r.route_id for r in risks if r.eligibility=='blocked'}
        recommendations=[r for r in recommendations if r.route_id not in blocked]
        for position, recommendation in enumerate(recommendations, 1):
            recommendation.final_rank=position
        warnings=['Candidate route geometries require visual review; not validated navigation routes.']
        if blocked:
            warnings.append('Explicit risk policy blocked routes from recommendations; their geometry and assessments remain available for discovery.')
        if recommendations and all(r.distance_match_warning for r in recommendations):
            warnings.append('No candidate reasonably matches your target distance; route geometry has not been shortened.')
        if not any(r.recommendation_score is not None for r in recommendations):
            warnings.append('No candidate has a usable non-blocked environmental assessment. Discovery uses non-environmental criteria; blocked routes are not recommended.')
        if preferences.duration_min>preferences.horizon_min: warnings.append('Forecast horizon does not cover the full run duration.')
        if any(p.is_mock for p in predictions): warnings.append('Rain probabilities are simulated fixtures, not trained forecasts.')
        if any(c.quality in {'stale','missing'} for c in conditions): warnings.append('Some observations are stale or unavailable.')
        if any(p.prediction_status=='forecast_unavailable' for p in predictions): warnings.append('Forecast unavailable: environmental risk uses current observations only, not conditions over the requested run duration.')
        result=Run(run_id=uuid4().hex,generated_at=datetime.now(timezone.utc),data_mode=self.mode,
            preferences=preferences,routes=routes,environment=environments,risks=risks,conditions=conditions,predictions=predictions,recommendations=recommendations,warnings=warnings)
        self.repository.save_run(result)
        return result
