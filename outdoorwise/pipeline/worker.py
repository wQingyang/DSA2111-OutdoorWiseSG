"""Continuous live ingestion using existing collectors and the repository port."""
import os
import threading
from outdoorwise.contracts.environment import utc_now
class CollectionWorker:
    def __init__(self,pipeline,tick_seconds=30,max_cycles=None,stop_event=None,emit=None):
        if pipeline.mode!='live':raise ValueError('The continuous worker requires live data mode')
        if tick_seconds<=0:raise ValueError('tick_seconds must be positive')
        if max_cycles is not None and max_cycles<1:raise ValueError('max_cycles must be positive')
        self.pipeline=pipeline;self.tick_seconds=tick_seconds;self.max_cycles=max_cycles
        self.stop=stop_event or threading.Event();self.emit=emit or (lambda event:None)
    def run(self):
        repo=self.pipeline.repository;cycles=0;last_report=None;started=utc_now().isoformat()
        def status(state,message=''):
            return {'state':state,'pid':os.getpid(),'source_kind':'live','started_at':started,
                'updated_at':utc_now().isoformat(),'completed_cycles':cycles,'last_report':last_report,'message':message}
        with repo.ingestion_worker_lock():
            repo.save_worker_status(status('running'));self.emit(status('running'))
            try:
                while not self.stop.is_set():
                    last_report=self.pipeline.refresh(due_only=True,should_stop=self.stop.is_set);cycles+=1
                    snapshot=status('running');repo.save_worker_status(snapshot);self.emit(snapshot)
                    if self.max_cycles is not None and cycles>=self.max_cycles:break
                    # Event.wait permits immediate shutdown between collection cycles.
                    self.stop.wait(self.tick_seconds)
            except Exception:
                # Disk/schema failures must stop, rather than claim healthy ingestion.
                repo.save_worker_status(status('failed','Worker stopped after an unexpected error; inspect stderr'))
                raise
            repo.save_worker_status(status('stopped'));self.emit(status('stopped'))
        return cycles
