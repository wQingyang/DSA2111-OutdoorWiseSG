"""Collector diagnostics/recovery with temporary CSVs and no provider requests."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import subprocess
import sys
import time
import pytest

from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.environment import IngestionRun, utc_now
from outdoorwise.contracts.ports import CollectionFailure, collection_error_category
from outdoorwise.pipeline.worker import CollectionWorker
from scripts.render_macos_collector import configuration


def test_launchd_configuration_is_foreground_supervised_and_secret_free(tmp_path):
    root = tmp_path/'project with spaces'
    spec = plistlib.loads(plistlib.dumps(configuration(root, tmp_path/'logs')))
    assert spec['KeepAlive'] is True and spec['RunAtLoad'] is True
    assert spec['ThrottleInterval'] == 30 and spec['ExitTimeOut'] == 180
    assert spec['ProgramArguments'] == ['/bin/zsh', str(root/'scripts/run_macos_collector.zsh')]
    assert spec['WorkingDirectory'] == str(root)
    assert spec['EnvironmentVariables'] == {'PYTHONUNBUFFERED': '1'}
    assert not (tmp_path/'logs').exists()  # Rendering is inert.


def test_failure_isolation_recovery_and_additive_diagnostics(tmp_path, monkeypatch):
    shutil.copytree(ROOT/'data/catalog', tmp_path/'catalog')
    pipe = build_pipeline(Settings(data_root=tmp_path, data_mode='live'))
    names = ['rainfall', 'wind-speed', 'wind-direction', 'air-temperature', 'relative-humidity', 'pm25', 'psi', 'wbgt']
    for collector, name in zip(pipe.collectors, names):
        payload = json.loads((ROOT/f'tests/fixtures/environment/{name}.json').read_text())
        monkeypatch.setattr(collector, 'collect', lambda c=collector, p=payload: (c.parse(p, utc_now()), 1))
    monkeypatch.setattr(pipe.config.collection, 'request_spacing_seconds', .001)
    pipe.refresh()
    before = {o.metric+o.location_id+o.observed_at.isoformat(): o.value for o in pipe.repository.environment_snapshot('live', utc_now())[1]}
    collect = pipe.collectors[0].collect
    calls = []
    def temporary_failure():
        calls.append(1)
        if len(calls) == 1:
            raise CollectionFailure('HTTP 503', 3)
        return collect()
    monkeypatch.setattr(pipe.collectors[0], 'collect', temporary_failure)
    monkeypatch.setattr(pipe.repository, 'source_due', lambda *args: True)
    events = []
    assert CollectionWorker(pipe, tick_seconds=.001, max_cycles=2, emit=events.append).run() == 2
    cycles = [e for e in events if e['event'] == 'heartbeat']
    rain1 = cycles[0]['source_diagnostics']['nea_rainfall']
    rain2 = cycles[1]['source_diagnostics']['nea_rainfall']
    assert rain1['last_status'] == 'failed' and rain1['consecutive_failures_this_process'] == 1
    assert rain2['last_status'] == 'success' and rain2['consecutive_failures_this_process'] == 0
    assert rain2['last_successful_fetch_at']
    assert all(s['status'] == 'success' for s in cycles[0]['last_report']['sources'][1:])
    assert events[0]['event'] == 'startup' and events[-1]['event'] == 'shutdown'
    after = {o.metric+o.location_id+o.observed_at.isoformat(): o.value for o in pipe.repository.environment_snapshot('live', utc_now())[1]}
    assert before == after
    source = pipe.repository.database_status()['sources']['nea_rainfall']
    assert source['consecutive_failures'] == 0 and source['last_error_category'] is None
    assert source['last_retained_fetch_at'] and source['last_successful_run_finished_at']
    now = utc_now()
    pipe.repository.record_failure(IngestionRun(run_id='diagnostic-failure', source='nea_rainfall', source_kind='live',
        started_at=now, finished_at=now, status='failed', error='HTTP 503'))
    source = pipe.repository.database_status()['sources']['nea_rainfall']
    assert source['consecutive_failures'] == 1 and source['last_error_category'] == 'http_503'
    assert source['last_successful_run_finished_at']
    assert collection_error_category('ConnectError: secret-token') == 'transport'
    assert collection_error_category('unknown secret-token') == 'unclassified'


@pytest.mark.parametrize('stop_signal', [signal.SIGTERM, signal.SIGHUP])
def test_killed_worker_releases_lease_and_restart_preserves_observations(tmp_path, stop_signal):
    shutil.copytree(ROOT/'data/catalog', tmp_path/'catalog')
    pipe = build_pipeline(Settings(data_root=tmp_path, data_mode='live'))
    collector = pipe.collectors[0]
    batch = collector.parse(json.loads((ROOT/'tests/fixtures/environment/rainfall.json').read_text()), utc_now())
    now = utc_now()
    pipe.repository.ingest(batch, IngestionRun(run_id='seed', source=collector.source, source_kind='live', started_at=now, finished_at=now, status='success'))
    for source in pipe.config.sources:
        pipe.repository.record_failure(IngestionRun(run_id=source, source=source, source_kind='live',
            started_at=now, finished_at=now, status='failed', error='fixture cooldown; no network'))
    paths = list(pipe.repository.runtime.glob('*observations.csv'))+list(pipe.repository.runtime.glob('*observation_versions.csv'))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    env = dict(os.environ, OUTDOORWISE_DATA_ROOT=str(tmp_path), OUTDOORWISE_DATA_MODE='live')
    command = [sys.executable, '-m', 'outdoorwise.cli', 'watch', '--tick-seconds', '60']
    if Path('/bin/zsh').exists():
        command = ['/bin/zsh', str(ROOT/'scripts/run_macos_collector.zsh')]
        env.update(OUTDOORWISE_ENV_FILE=str(tmp_path/'absent.env'), OUTDOORWISE_COLLECTOR_TICK_SECONDS='60')
    def start():
        proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            status_path = pipe.repository.runtime/'collection_worker.json'
            state = json.loads(status_path.read_text()) if status_path.exists() else {}
            if state.get('pid') == proc.pid and state.get('completed_cycles', 0) >= 1:
                return proc
            if proc.poll() is not None:
                raise AssertionError(proc.communicate())
            time.sleep(.05)
        proc.kill(); proc.communicate()
        raise AssertionError('Worker did not initialize')
    proc = start()
    try:
        proc.kill(); proc.communicate(timeout=5)
        assert proc.returncode != 0
        # SIGKILL cannot emit shutdown: persisted running state is deliberately not trusted.
        assert json.loads((pipe.repository.runtime/'collection_worker.json').read_text())['state'] == 'running'
        proc = start()
        proc.send_signal(stop_signal)
        out, error = proc.communicate(timeout=5)
        assert proc.returncode == 0, error
        assert json.loads(out.splitlines()[-1])['stop_reason'] == signal.Signals(stop_signal).name
        assert json.loads(out.splitlines()[0])['event'] == 'startup'
        assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    finally:
        if proc.poll() is None:
            proc.kill(); proc.communicate()


def test_unknown_api_response_is_disclosed_and_remains_discovery(tmp_path):
    from fastapi.testclient import TestClient
    from outdoorwise.api.app import create_app
    shutil.copytree(ROOT/'data/catalog', tmp_path/'catalog')
    with TestClient(create_app(Settings(data_root=tmp_path, data_mode='live'))) as client:
        result = client.post('/api/recommendations', json={'target_distance_km': 5}).json()
    assert len(result['recommendations']) == 12
    assert all(r['risk_score'] is None and r['eligibility'] == 'unknown' for r in result['risks'])
    assert all(r['recommendation_score'] is None and r['ranking_method'] == 'legacy_non_environmental' for r in result['recommendations'])
    assert any('Discovery uses non-environmental criteria' in warning for warning in result['warnings'])
