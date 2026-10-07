import shutil,threading
from datetime import timedelta
import pytest
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import Settings,ROOT
from outdoorwise.pipeline.worker import CollectionWorker
from outdoorwise.contracts.environment import IngestionRun,utc_now
@pytest.fixture
def live_pipeline(tmp_path):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog')
    return build_pipeline(Settings(data_root=tmp_path,data_mode='live'))
def test_worker_preserves_due_checks_and_shutdown(live_pipeline):
    events=[];calls=[]
    def refresh(**kwargs):
        calls.append(kwargs);return {'status':'partial','sources':[],'routes':2,'metrics':20}
    live_pipeline.refresh=refresh
    assert CollectionWorker(live_pipeline,tick_seconds=.001,max_cycles=2,emit=events.append).run()==2
    assert len(calls)==2 and all(c['due_only'] for c in calls)
    status=live_pipeline.repository.database_status()['worker']
    assert status['state']=='stopped' and status['completed_cycles']==2
    assert events[-1]['state']=='stopped'
def test_single_worker_lease(live_pipeline):
    with live_pipeline.repository.ingestion_worker_lock():
        with pytest.raises(RuntimeError,match='already owns'):
            with live_pipeline.repository.ingestion_worker_lock():pass
    with live_pipeline.repository.ingestion_worker_lock():pass
def test_failure_cooldown_and_restart(live_pipeline):
    repo=live_pipeline.repository;now=utc_now()
    repo.record_failure(IngestionRun(run_id='failure',source='nea_rainfall',source_kind='live',started_at=now,finished_at=now,status='failed',error='HTTP 503'))
    assert not repo.source_due('nea_rainfall','live',300,now+timedelta(seconds=30))
    restarted=build_pipeline(Settings(data_root=repo.root,data_mode='live'))
    assert not restarted.repository.source_due('nea_rainfall','live',300,now+timedelta(seconds=299))
    assert restarted.repository.source_due('nea_rainfall','live',300,now+timedelta(seconds=300))
def test_worker_error_and_stop(live_pipeline):
    def broken(**kw):raise OSError('disk error')
    live_pipeline.refresh=broken
    with pytest.raises(OSError):CollectionWorker(live_pipeline,max_cycles=1).run()
    assert live_pipeline.repository.database_status()['worker']['state']=='failed'
    stop=threading.Event();stop.set()
    assert CollectionWorker(live_pipeline,stop_event=stop).run()==0
    assert live_pipeline.repository.database_status()['worker']['state']=='stopped'
def test_demo_and_invalid_options(live_pipeline):
    with pytest.raises(ValueError):CollectionWorker(live_pipeline,tick_seconds=0)
    with pytest.raises(ValueError):CollectionWorker(live_pipeline,max_cycles=0)
    live_pipeline.mode='demo'
    with pytest.raises(ValueError,match='live'):CollectionWorker(live_pipeline)
def test_cli_sigterm_and_duplicate_worker(live_pipeline):
    import os,subprocess,sys,time,json,signal
    repo=live_pipeline.repository;now=utc_now()
    for source in live_pipeline.config.sources:
        repo.record_failure(IngestionRun(run_id=source,source=source,source_kind='live',started_at=now,finished_at=now,status='failed',error='Test fixture: skip external requests'))
    env=os.environ.copy();env['OUTDOORWISE_DATA_ROOT']=str(repo.root);env['OUTDOORWISE_DATA_MODE']='live';env['OUTDOORWISE_AGENT_MODE']='demo'
    with repo.ingestion_worker_lock():
        duplicate=subprocess.run([sys.executable,'-m','outdoorwise.cli','watch','--max-cycles','1'],env=env,capture_output=True,text=True,timeout=10)
        assert duplicate.returncode==1 and 'already owns' in duplicate.stderr
    proc=subprocess.Popen([sys.executable,'-m','outdoorwise.cli','watch','--tick-seconds','60'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            worker=repo.database_status()['worker']
            if worker and worker['completed_cycles']>=1:break
            if proc.poll() is not None:pytest.fail('Worker exited before first cycle')
            time.sleep(.05)
        else:pytest.fail('Worker did not complete first cycle')
        proc.send_signal(signal.SIGTERM)
        output,error=proc.communicate(timeout=5)
        assert proc.returncode==0,error
        assert json.loads(output.splitlines()[-1])['state']=='stopped'
        assert repo.database_status()['worker']['state']=='stopped'
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
