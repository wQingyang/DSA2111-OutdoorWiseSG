import csv,json,shutil,re
from datetime import datetime,timedelta,timezone
import pytest
from outdoorwise.config import ROOT,Settings
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.storage.repository import FileRepository,TABLES,OBSERVATION_TABLES,VERSION_TABLES,csv_datetime,key
from outdoorwise.contracts.environment import IngestionRun
from outdoorwise.collectors.demo import DemoEnvironmentCollector
@pytest.fixture
def root(tmp_path):
    shutil.copytree(ROOT/'data/catalog',tmp_path/'catalog');return tmp_path
def log(batch):return IngestionRun(run_id='test',source=batch.source,source_kind=batch.observations[0].source_kind,started_at=batch.fetched_at,finished_at=batch.fetched_at,status='success')
def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def test_utc_conversion_and_no_fraction(root):
    repo=FileRepository(root);batch,_=DemoEnvironmentCollector('nea_rainfall').collect()
    instant=datetime.fromisoformat('2026-10-05T03:38:28.869141+00:00')
    batch=batch.model_copy(update={'fetched_at':instant,'observations':[o.model_copy(update={'observed_at':instant,'fetched_at':instant,'source_updated_at':instant}) for o in batch.observations]})
    repo.ingest(batch,log(batch))
    rows=read(repo.runtime/'weather_observations.csv')
    assert rows[0]['observed_at']==rows[0]['fetched_at']==rows[0]['source_updated_at']=='2026-10-05T11:38:28'
    # Identical fractional source timestamps must not produce false revisions.
    assert repo.ingest(batch,log(batch)).revised_records==0
    snap=repo.environment_snapshot('demo',instant+timedelta(seconds=1))[1]
    assert snap[0].observed_at.utcoffset()==timedelta(hours=8)
    assert key(snap[0])==key(batch.observations[0])
    with pytest.raises(ValueError):
        from outdoorwise.contracts.environment import timestamp
        timestamp('2026-10-05T11:38:28')
def test_current_tables_startup_is_repeatable(root):
    pipeline=build_pipeline(Settings(data_root=root,data_mode='demo'))
    pipeline.refresh()
    before={name:(root/'runtime'/name).read_bytes() for name in TABLES}
    FileRepository(root)
    assert before=={name:(root/'runtime'/name).read_bytes() for name in TABLES}
    assert set(path.name for path in (root/'runtime').glob('*.csv'))==set(TABLES)
def test_all_categories_and_time_columns(root):
    pipeline=build_pipeline(Settings(data_root=root,data_mode='demo'));pipeline.refresh();pipeline.run(__import__('outdoorwise.contracts.models',fromlist=['Preferences']).Preferences())
    expected={'weather':10,'air_quality':6,'heat_stress':4}
    for group,name in OBSERVATION_TABLES.items():
        assert len(read(root/'runtime'/name))==expected[group]
        assert len(read(root/'runtime'/VERSION_TABLES[group]))==expected[group]
    for name in TABLES:
        for row in read(root/'runtime'/name):
            for field,value in row.items():
                if (field.endswith('_at') or field=='as_of') and value:
                    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',value)
    assert len(pipeline.get_route_environment('marina_bay').metrics)==10
    assert pipeline.repository.database_status('demo')['observation_records']==20
