from datetime import datetime,timedelta,timezone
import json,shutil,csv
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from outdoorwise.config import Settings,ROOT
from outdoorwise.bootstrap import build_pipeline,COLLECTORS
from outdoorwise.api.app import create_app
from outdoorwise.contracts.models import Preferences
from outdoorwise.contracts.environment import IngestionRun,CollectionBatch,EnvironmentObservation,utc_now
from outdoorwise.collectors.base import CollectionFailure
@pytest.fixture
def pipeline(tmp_path):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog')
    return build_pipeline(Settings(data_root=tmp_path,data_mode='demo'))
def log(batch):return IngestionRun(run_id='test',source=batch.source,source_kind=batch.observations[0].source_kind,started_at=batch.fetched_at,finished_at=batch.fetched_at,status='success')
def test_demo_pipeline_api_agent(pipeline):
    report=pipeline.refresh();assert report['status']=='success' and report['metrics']==len(pipeline.repository.load_routes()) * 10
    run=pipeline.run(Preferences());assert {e.route_id for e in run.environment}=={r.route_id for r in pipeline.repository.load_routes()} and all(p.is_mock for p in run.predictions)
    assert all(len(e.metrics) == 10  for e in run.environment)
    assert {m.location_id for m in pipeline.repository.environment_snapshot('demo', utc_now())[1] if m.source == 'nea_pm25'} == {'north', 'south', 'east', 'west', 'central'}
    assert all(r.risk_score is not None and r.recommendation_score is not None for r in run.recommendations)
    distances={r.route_id:r.distance_km for r in run.routes};assert distances['marina_bay']==3.729 and distances['woodlands_waterfront']==1.45
    with TestClient(create_app(Settings(data_root=pipeline.repository.root,data_mode='demo'))) as client:
        assert client.get('/').status_code==200
        assert len(client.get('/api/routes/marina_bay/environment').json()['metrics'])==10
        assert client.get('/api/routes/marina_bay/environment?as_of=2026-10-05T10:00:00').status_code==422
        assert client.get('/api/routes/bad/environment').status_code==404
        assert client.post('/api/recommendations',json={'horizon_min':45}).status_code==422
        chat=client.post('/api/chat',json={'message':'compare'}).json()
        assert len(chat['trace'])==4 and len(chat['run']['environment'])==len(pipeline.repository.load_routes())
        assert 'environment' in chat['trace'][1]['result']

def test_demo_coverage_uses_only_current_synthetic_sources(pipeline):
    pipeline.refresh()
    locations, observations, _ = pipeline.repository.environment_snapshot('demo', utc_now())
    assert {location.location_id for location in locations if location.source == 'nea_pm25'} == {'north', 'south', 'east', 'west', 'central'}
    assert {observation.source_kind for observation in observations} == {'demo'}
    assert not any('snapshot' in str(value).lower() for value in observations for value in (value.source, value.location_id))

def test_demo_freshness_guard_collects_once_then_reuses_fresh_data(pipeline, monkeypatch):
    calls=[]
    original=pipeline.refresh
    def refresh(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline, 'refresh', refresh)
    pipeline.ensure_demo_data_fresh()
    pipeline.ensure_demo_data_fresh()
    assert len(calls)==1
    assert {o.location_id for o in pipeline.repository.environment_snapshot('demo', utc_now())[1] if o.source == 'nea_pm25'} == {'north','south','east','west','central'}

def test_live_pipeline_never_uses_demo_freshness_guard(tmp_path, monkeypatch):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog')
    pipeline=build_pipeline(Settings(data_root=tmp_path,data_mode='live'))
    monkeypatch.setattr(pipeline, 'refresh', lambda: (_ for _ in ()).throw(AssertionError('live refresh invoked')))
    assert pipeline.ensure_demo_data_fresh() is None
def test_dedup_revisions_asof(pipeline):
    batch,_=pipeline.collectors[0].collect();repo=pipeline.repository
    first=repo.ingest(batch,log(batch));again=repo.ingest(batch,log(batch))
    assert first.inserted_records==5 and again.inserted_records==0 and again.unchanged_records==5
    after=batch.fetched_at+timedelta(minutes=1)
    changed=batch.model_copy(update={'fetched_at':after,'observations':[o.model_copy(update={'fetched_at':after,'value':8}) for o in batch.observations]})
    assert repo.ingest(changed,log(changed)).revised_records==5
    assert {o.value for o in repo.environment_snapshot('demo',batch.fetched_at)[1]}=={0,1.2}
    assert {o.value for o in repo.environment_snapshot('demo',after)[1]}=={8}
    assert len(list(csv.DictReader((repo.runtime/'weather_observations.csv').open())))==5
    assert len(list(csv.DictReader((repo.runtime/'weather_observation_versions.csv').open())))==10
    assert repo.ingest(batch,log(batch)).revised_records==0
    offset=timezone(timedelta(hours=8))
    alternate=batch.model_copy(update={'observations':[o.model_copy(update={'observed_at':o.observed_at.astimezone(offset)}) for o in batch.observations]})
    assert repo.ingest(alternate,log(alternate)).inserted_records==0
def test_failure_isolation(pipeline):
    pipeline.refresh();original=pipeline.collectors[0]
    class Broken:
        source=original.source
        def collect(self):raise CollectionFailure('HTTP 503',3)
    pipeline.collectors[0]=Broken();report=pipeline.refresh()
    assert report['status']=='partial' and len(report['sources'])==8
    assert report['sources'][0]['status']=='failed' and all(s['status']=='success' for s in report['sources'][1:])
    # Demo data remains labelled demo, including after failures.
    assert pipeline.get_route_environment('marina_bay').metrics[0].delivery=='demo'
def test_null_missing_stale_and_future(pipeline):
    assert all(m.state=='missing' and m.value is None for m in pipeline.get_route_environment('marina_bay').metrics)
    pipeline.refresh();future=utc_now()+timedelta(hours=3)
    env=pipeline.get_route_environment('marina_bay',future)
    assert all(m.state=='stale' for m in env.metrics)
    assert all(m.state=='missing' for m in pipeline.get_route_environment('marina_bay',utc_now()-timedelta(days=1)).metrics)
    batch,_=pipeline.collectors[0].collect();data=batch.observations[0].model_dump();data['unit']='knots'
    with pytest.raises(ValidationError):EnvironmentObservation.model_validate(data)
    data=batch.observations[0].model_dump();data['observed_at']=datetime.now().isoformat()
    with pytest.raises(ValidationError):EnvironmentObservation.model_validate(data)
    with pytest.raises(ValueError):pipeline.get_route_environment('marina_bay',datetime.now())
def test_real_recorded_collectors_and_matching(tmp_path):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog');pipe=build_pipeline(Settings(data_root=tmp_path,data_mode='live'))
    names=['rainfall','wind-speed','wind-direction','air-temperature','relative-humidity','pm25','psi','wbgt']
    now=utc_now()
    for collector,name in zip(pipe.collectors,names):
        payload=json.loads((ROOT/'tests/fixtures/environment'/f'{name}.json').read_text())
        batch=collector.parse(payload,now);assert batch.observations and all(o.source_kind=='live' for o in batch.observations)
        assert pipe.repository.ingest(batch,log(batch)).inserted_records==len(batch.observations)
        assert pipe.repository.ingest(batch,log(batch)).inserted_records==0
    run=pipe.run(Preferences());assert {e.route_id for e in run.environment}=={r.route_id for r in pipe.repository.load_routes()}
    regions=pipe.config.matching.route_regions
    route_ids={r.route_id for r in pipe.repository.load_routes()}
    assert route_ids <= set(regions)
    for env in run.environment:
        region=regions[env.route_id]
        metrics={m.metric:m for m in env.metrics}
        assert len(metrics)==10 and all(m.state!='missing' for m in metrics.values())
        assert all(metrics[m].location_id==region for m in ['pm25','psi','pm10'])
        assert metrics['heat_stress_level'].category_value in ['Low','Moderate','High']
    assert all(p.status=='unavailable' and not p.is_mock for p in run.predictions)
    wbgt=json.loads((ROOT/'tests/fixtures/environment/wbgt.json').read_text());batch=pipe.collectors[-1].parse(wbgt,now)
    assert {o.metric for o in batch.observations}=={'wbgt','heat_stress_level'}
    wind=json.loads((ROOT/'tests/fixtures/environment/wind-speed.json').read_text());wind['data']['readingUnit']='m/s'
    with pytest.raises(ValueError):pipe.collectors[1].parse(wind,now)
def test_atomic_recovery_and_writer_lock(pipeline):
    import concurrent.futures
    repo=pipeline.repository;batch,_=pipeline.collectors[0].collect()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:repo.ingest(batch,log(batch)),range(8)))
    assert len(repo.environment_snapshot('demo',utc_now())[1])==5
    assert not list(repo.runtime.glob('*.tmp'))
    journal=repo.runtime/'.pending_csv_transaction.json'
    journal.write_text(json.dumps({'ingestion_runs.csv':[]}))
    from outdoorwise.storage.repository import FileRepository
    recovered=FileRepository(repo.root);assert not journal.exists() and recovered.ingestion_history()==[]
def test_module_output_validation(pipeline):
    pipeline.refresh()
    class Bad:
        def predict(self,*args):return []
    pipeline.predictor=Bad()
    with pytest.raises(ValueError,match='exactly one'):pipeline.run(Preferences())
def test_tool_allowlist(pipeline):
    from outdoorwise.agent.tools import ToolRegistry
    registry=ToolRegistry(pipeline,Preferences())
    with pytest.raises(ValueError):registry.call('delete',{})
    with pytest.raises(ValueError):registry.call('rank_routes',{'arbitrary':1})
def test_live_failure_uses_cache_and_due(tmp_path):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog')
    pipe=build_pipeline(Settings(data_root=tmp_path,data_mode='live'));now=utc_now()
    batch=pipe.collectors[0].parse(json.loads((ROOT/'tests/fixtures/environment/rainfall.json').read_text()),now)
    pipe.repository.ingest(batch,log(batch))
    assert not pipe.repository.source_due(batch.source,'live',300,now+timedelta(seconds=1))
    failure=log(batch).model_copy(update={'status':'failed','finished_at':now+timedelta(seconds=1),'error':'HTTP 503'})
    pipe.repository.record_failure(failure)
    metric=pipe.get_route_environment('marina_bay',now+timedelta(seconds=2)).metrics[0]
    assert metric.delivery=='cache' and metric.source_kind=='live' and metric.value is not None
    assert all(m.state=='missing' for m in pipe.get_route_environment('woodlands_waterfront',now+timedelta(seconds=2)).metrics[1:])
def test_retry_transport_and_llm_tool_loop(pipeline,monkeypatch):
    from unittest.mock import Mock
    import httpx
    collector=COLLECTORS['nea_rainfall'](pipeline.config.sources['nea_rainfall'],pipeline.config.collection)
    request=httpx.Request('GET',collector.config.url)
    payload=json.loads((ROOT/'tests/fixtures/environment/rainfall.json').read_text())
    responses=[httpx.Response(429,request=request,headers={'Retry-After':'0'}),httpx.Response(200,request=request,json=payload)]
    client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False);client.get.side_effect=responses
    monkeypatch.setattr('outdoorwise.collectors.base.httpx.Client',lambda **kw:client)
    monkeypatch.setattr('outdoorwise.collectors.base.time.sleep',lambda s:None)
    batch,attempts=collector.collect();assert attempts==2 and len(batch.observations)>20
    pipeline.refresh()
    from outdoorwise.agent.service import AgentService
    from outdoorwise.contracts.models import ChatRequest
    replies=[{'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'1','type':'function','function':{'name':'get_route_environment','arguments':'{"route_id":"marina_bay"}'}},{'id':'2','type':'function','function':{'name':'rank_routes','arguments':'{}'}}]}}]}, {'choices':[{'message':{'role':'assistant','content':'Structured output explanation.'}}]}]
    client.post.side_effect=[Mock(json=Mock(return_value=r),raise_for_status=Mock()) for r in replies]
    result=AgentService(pipeline,Settings(data_root=pipeline.repository.root,data_mode='demo',agent_mode='llm',llm_model='test',llm_api_key='test')).chat(ChatRequest(message='compare'))
    assert len(result.trace)==2 and set(result.recommended_route_ids)=={r.route_id for r in pipeline.repository.load_routes()}
    assert len(result.trace[0].result['environment']['metrics'])==10
    # This checks the tool loop only, not a real provider call.
