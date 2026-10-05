from datetime import timezone
"""CSV adapter: one locked writer, atomic replacement, recoverable multi-file journal."""
import csv,json,os,threading,fcntl
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from typing import get_args
from outdoorwise.contracts.models import Route,Run
from outdoorwise.contracts.environment import (Location,EnvironmentObservation,IngestionRun,RouteSourceMapping,RouteMetric,utc_now,timestamp)
TABLES={
    "locations.csv":Location,
    "environment_observations.csv":EnvironmentObservation,
    "environment_observation_versions.csv":EnvironmentObservation,
    "route_source_mapping.csv":RouteSourceMapping,
    "route_environment_latest.csv":RouteMetric,
    "ingestion_runs.csv":IngestionRun,
}
LOCKS={};LOCKS_GUARD=threading.Lock()
def key(o):return (o.source,o.location_id,o.observed_at.astimezone(timezone.utc).isoformat(),o.metric,o.aggregation_window,o.source_kind)
def typed(model,row):
    return model.model_validate({k:(None if v=="" and type(None) in get_args(model.model_fields[k].annotation) else v) for k,v in row.items()})
class FileRepository:
    def __init__(self,root: Path):
        self.root=root;self.runtime=root/"runtime";self.runtime.mkdir(parents=True,exist_ok=True)
        with LOCKS_GUARD:self.lock=LOCKS.setdefault(str(self.runtime.resolve()),threading.RLock())
        self.local=threading.local()
        with self._guard():
            journal=self.runtime/'.pending_csv_transaction.json'
            if journal.exists():
                self._replay(json.loads(journal.read_text()));journal.unlink()
            for name,model in TABLES.items():
                if not (self.runtime/name).exists():self._atomic_csv(name,[],list(model.model_fields))
            self._migrate_v1()
    @contextmanager
    def _guard(self):
        with self.lock:
            depth=getattr(self.local,'depth',0)
            if depth==0:
                self.local.fd=(self.runtime/'.writer.lock').open('a')
                fcntl.flock(self.local.fd,fcntl.LOCK_EX)
            self.local.depth=depth+1
            try:yield
            finally:
                self.local.depth-=1
                if depth==0:
                    fcntl.flock(self.local.fd,fcntl.LOCK_UN);self.local.fd.close()
    def _read(self,name):
        with (self.runtime/name).open(newline='') as f:return list(csv.DictReader(f))
    def _atomic_json(self,name,data):
        path=self.runtime/name;temp=path.with_suffix('.'+uuid4().hex+'.tmp')
        try:
            with temp.open('w') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
    def _atomic_csv(self,name,rows,fields):
        path=self.runtime/name;temp=path.with_suffix('.'+uuid4().hex+'.tmp')
        try:
            with temp.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows);f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
    def _replay(self,tables):
        for name,rows in tables.items():
            self._atomic_csv(name,rows,list(TABLES[name].model_fields))
    def _commit(self,tables):
        # Caller holds writer lock; journal is durable BEFORE any replacement.
        self._atomic_json('.pending_csv_transaction.json',tables)
        self._replay(tables)
        (self.runtime/'.pending_csv_transaction.json').unlink()
    def _migrate_v1(self):
        path=self.runtime/'observations.csv'
        if not path.exists() or self._read('environment_observations.csv'):return
        with path.open(newline='') as f:legacy=list(csv.DictReader(f))
        rows=[];locations={}
        for r in legacy:
            if r['metric']!='rainfall':continue
            origin='demo' if r['source']=='demo_fixture' else 'live';fetched=timestamp(r['collected_at'])
            loc=Location(source='nea_rainfall',location_id=r['station_id'],name=r['station_id'],location_type='station',
                lon=r['lon'],lat=r['lat'],source_kind=origin,metadata_updated_at=fetched)
            locations[(loc.source,loc.location_id,origin)]=loc
            rows.append(EnvironmentObservation(source='nea_rainfall',location_id=loc.location_id,metric='rainfall',
                value=r['value'],unit='mm',aggregation_window='PT5M',source_kind=origin,
                observed_at=timestamp(r['observed_at']),fetched_at=fetched,first_fetched_at=fetched))
        if rows:
            unique={key(o):o for o in rows};serial=[x.model_dump(mode='json') for x in unique.values()]
            self._commit({'locations.csv':[x.model_dump(mode='json') for x in locations.values()],
                'environment_observations.csv':serial,'environment_observation_versions.csv':serial})
    def load_routes(self) -> list[Route]:
        catalog = self.root / "catalog"
        with (catalog / "routes.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        routes=[]
        for row in rows:
            path = (catalog / row["geometry_file"]).resolve()
            if path.parent != catalog.resolve():
                raise ValueError("Geometry must be a file directly in catalog")
            data=json.loads(path.read_text())
            if data["properties"]["route_id"] != row["route_id"]:
                raise ValueError("CSV and GeoJSON IDs disagree")
            for lon,lat in data["geometry"]["coordinates"]:
                if not (-180<=lon<=180 and -90<=lat<=90):
                    raise ValueError("Invalid GeoJSON longitude/latitude")
            routes.append(Route(route_id=row["route_id"], name=row["name"], kind=row["kind"],
                distance_km=float(row["distance_km"]), status=row["status"], geometry=data["geometry"],
                attribution=data["properties"].get("attribution", "")))
        if len({r.route_id for r in routes}) != len(routes):
            raise ValueError("Duplicate route IDs")
        return routes

    def ingestion_history(self,source_kind=None):
        with self._guard():
            rows=[typed(IngestionRun,r) for r in self._read('ingestion_runs.csv')]
        return [r for r in rows if source_kind is None or r.source_kind==source_kind]
    def source_due(self,source,source_kind,interval_seconds,as_of):
        successes=[r for r in self.ingestion_history(source_kind) if r.source==source and r.status=='success']
        return not successes or (as_of-max(r.finished_at for r in successes)).total_seconds()>=interval_seconds
    def record_failure(self,run):
        with self._guard():
            rows=self._read('ingestion_runs.csv');rows.append(run.model_dump(mode='json'));self._commit({'ingestion_runs.csv':rows})
    def ingest(self,batch,run):
        with self._guard():
            locations={(l.source,l.location_id,l.source_kind):l for l in [typed(Location,r) for r in self._read('locations.csv')]}
            for l in batch.locations:locations[(l.source,l.location_id,l.source_kind)]=l
            current={key(o):o for o in [typed(EnvironmentObservation,r) for r in self._read('environment_observations.csv')]}
            versions=self._read('environment_observation_versions.csv');inserted=revised=unchanged=0
            for incoming in batch.observations:
                k=key(incoming);previous=current.get(k)
                if previous is None:
                    o=incoming.model_copy(update={'first_fetched_at':incoming.fetched_at,'revision':1})
                    current[k]=o;versions.append(o.model_dump(mode='json'));inserted+=1;continue
                # Ignore late/out-of-order revision responses; equal update timestamps permit corrections.
                if previous.source_updated_at and incoming.source_updated_at and incoming.source_updated_at<previous.source_updated_at:
                    unchanged+=1;continue
                if incoming.fetched_at<previous.fetched_at:unchanged+=1;continue
                fields=('value','category_value','unit','aggregation_window','raw_value','raw_unit','source_updated_at')
                changed=any(getattr(previous,f)!=getattr(incoming,f) for f in fields)
                if changed:
                    o=incoming.model_copy(update={'revision':previous.revision+1,'first_fetched_at':incoming.fetched_at})
                    current[k]=o;versions.append(o.model_dump(mode='json'));revised+=1
                else:
                    current[k]=previous.model_copy(update={'fetched_at':incoming.fetched_at});unchanged+=1
            run=run.model_copy(update={'received_records':len(batch.observations),'inserted_records':inserted,
                'revised_records':revised,'unchanged_records':unchanged})
            logs=self._read('ingestion_runs.csv');logs.append(run.model_dump(mode='json'))
            self._commit({'locations.csv':[x.model_dump(mode='json') for x in locations.values()],
                'environment_observations.csv':[x.model_dump(mode='json') for x in current.values()],
                'environment_observation_versions.csv':versions,'ingestion_runs.csv':logs})
            return run
    def environment_snapshot(self,source_kind,as_of):
        with self._guard():
            locations=[typed(Location,r) for r in self._read('locations.csv')]
            versions=[typed(EnvironmentObservation,r) for r in self._read('environment_observation_versions.csv')]
            current=[typed(EnvironmentObservation,r) for r in self._read('environment_observations.csv')]
            logs=[typed(IngestionRun,r) for r in self._read('ingestion_runs.csv')]
        # Bitemporal availability: cannot expose a revision first fetched after as_of.
        eligible={}
        for o in versions:
            if o.source_kind!=source_kind or o.observed_at>as_of or (o.first_fetched_at or o.fetched_at)>as_of:continue
            if o.source_updated_at and o.source_updated_at>as_of:continue
            k=key(o)
            if k not in eligible or o.revision>eligible[k].revision:eligible[k]=o
        for o in current:
            k=key(o)
            if k in eligible and o.revision==eligible[k].revision and o.fetched_at<=as_of:eligible[k]=o
        return ([l for l in locations if l.source_kind==source_kind],list(eligible.values()),
                [r for r in logs if r.source_kind==source_kind and r.finished_at<=as_of])
    def save_route_environment(self,environments,mappings):
        with self._guard():
            self._commit({'route_environment_latest.csv':[m.model_dump(mode='json') for e in environments for m in e.metrics],
                'route_source_mapping.csv':[m.model_dump(mode='json') for m in mappings]})
    def save_run(self,run:Run):
        with self._guard():
            self._atomic_json('latest_run.json',run.model_dump(mode='json'))
            self._atomic_json('run_'+run.run_id+'.json',run.model_dump(mode='json'))
            # Future predictions are stored separately, never in the observation long table.
            self._atomic_json('predictions_latest.json',[x.model_dump(mode='json') for x in run.predictions])
