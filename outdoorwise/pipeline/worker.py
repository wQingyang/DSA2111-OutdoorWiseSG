"""Continuous live ingestion using existing collectors and the repository port."""
import os
import threading
from outdoorwise.contracts.environment import utc_now
from outdoorwise.contracts.ports import collection_error_category
class CollectionWorker:
    def __init__(self,pipeline,tick_seconds=30,max_cycles=None,stop_event=None,emit=None):
        if pipeline.mode!='live':raise ValueError('The continuous worker requires live data mode')
        if tick_seconds<=0:raise ValueError('tick_seconds must be positive')
        if max_cycles is not None and max_cycles<1:raise ValueError('max_cycles must be positive')
        self.pipeline=pipeline;self.tick_seconds=tick_seconds;self.max_cycles=max_cycles
        self.stop=stop_event or threading.Event();self.emit=emit or (lambda event:None)
        self.stop_reason='requested'
    def request_stop(self,reason='requested'):
        self.stop_reason=reason if reason in {'SIGINT','SIGTERM','SIGHUP','requested'} else 'requested'
        self.stop.set()
    def run(self):
        repo=self.pipeline.repository;cycles=0;last_report=None;started=utc_now().isoformat()
        cycle_started=cycle_finished=None;sources={}
        def status(state,message='',event='heartbeat'):
            return {'state':state,'pid':os.getpid(),'source_kind':'live','started_at':started,
                'updated_at':utc_now().isoformat(),'completed_cycles':cycles,'last_report':last_report,'message':message,
                'event':event,'last_cycle_started_at':cycle_started,'last_cycle_finished_at':cycle_finished,
                'stop_reason':self.stop_reason if state=='stopped' else None,'source_diagnostics':sources.copy()}
        with repo.ingestion_worker_lock():
            snapshot=status('running',event='startup');repo.save_worker_status(snapshot);self.emit(snapshot)
            try:
                while not self.stop.is_set():
                    cycle_started=utc_now().isoformat()
                    last_report=self.pipeline.refresh(due_only=True,should_stop=self.stop.is_set);cycles+=1
                    cycle_finished=utc_now().isoformat()
                    for source in last_report.get('sources',[]):
                        previous=sources.get(source['source'],{})
                        sources[source['source']]={
                            'last_attempt_started_at':source['started_at'],
                            'last_attempt_finished_at':source['finished_at'],
                            'last_successful_fetch_at':source.get('fetched_at') if source['status']=='success' else previous.get('last_successful_fetch_at'),
                            'last_ingestion_run_finished_at':source['finished_at'] if source['status']=='success' else previous.get('last_ingestion_run_finished_at'),
                            'consecutive_failures_this_process':previous.get('consecutive_failures_this_process',0)+1 if source['status']=='failed' else 0,
                            'last_error_category':collection_error_category(source.get('error')) if source['status']=='failed' else None,
                            'last_status':source['status']}
                    snapshot=status('running');repo.save_worker_status(snapshot);self.emit(snapshot)
                    if self.max_cycles is not None and cycles>=self.max_cycles:break
                    # Event.wait permits immediate shutdown between collection cycles.
                    self.stop.wait(self.tick_seconds)
            except Exception:
                # Disk/schema failures must stop, rather than claim healthy ingestion.
                snapshot=status('failed','Worker stopped after an unexpected error; inspect stderr',event='failure')
                repo.save_worker_status(snapshot);self.emit(snapshot)
                raise
            snapshot=status('stopped',event='shutdown');repo.save_worker_status(snapshot);self.emit(snapshot)
        return cycles
