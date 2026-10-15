"""Build explicitly synthetic UI responses through real Sprint 1 contracts.

Uses recorded payload parsers and temporary storage; no external collection or
real user data. Run from repository root with PYTHONPATH=.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.environment import IngestionRun
from outdoorwise.contracts.models import Preferences
from outdoorwise.contracts.risk import BlockingRule
from outdoorwise.personalization.ranking import rank_candidates

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def build():
    with TemporaryDirectory(prefix='outdoorwise-ui-fixture-') as directory:
        data_root = Path(directory)
        shutil.copytree(ROOT/'data/catalog', data_root/'catalog')
        pipeline = build_pipeline(Settings(data_root=data_root, data_mode='live'))
        for collector, name in zip(pipeline.collectors, ['rainfall', 'wind-speed', 'wind-direction', 'air-temperature', 'relative-humidity', 'pm25', 'psi', 'wbgt']):
            batch = collector.parse(json.loads((ROOT/'tests/fixtures/environment'/f'{name}.json').read_text()), NOW)
            batch = batch.model_copy(update={'observations': [o.model_copy(update={'observed_at': NOW, 'fetched_at': NOW, 'source_updated_at': NOW}) for o in batch.observations]})
            pipeline.repository.ingest(batch, IngestionRun(run_id=name, source=batch.source, source_kind='live', started_at=NOW, finished_at=NOW, status='success'))
        envs = pipeline.environment_service.get_all(NOW)
        for env in envs:
            for m in env.metrics:
                if m.metric == 'rainfall': m.value = 0
                if m.metric == 'wbgt': m.value = 26
                if m.metric == 'heat_stress_level': m.category_value = 'Low'
                if m.metric == 'pm25': m.value = 0
                if env.route_id == 'east_coast':
                    if m.metric == 'wbgt': m.value = 35
                    if m.metric == 'heat_stress_level': m.category_value = 'High'
                    if m.metric == 'wind_speed': m.station_distance_km = 5.193
                if env.route_id == 'woodlands_waterfront' and m.metric == 'rainfall':
                    m.value = None; m.state = 'missing'
                if env.route_id == 'bishan_ang_mo_kio':
                    m.observed_at = NOW-timedelta(hours=3); m.fetched_at = m.observed_at; m.source_updated_at = m.observed_at; m.state = 'stale'
                if env.route_id == 'bedok_reservoir': m.fetched_at = NOW+timedelta(minutes=1)
                if env.route_id == 'jurong_lake_gardens':
                    if m.metric == 'wbgt': m.value = 36
                    if m.metric == 'heat_stress_level': m.category_value = 'High'
        pipeline.config.risk.blocking_rules = [BlockingRule(enabled=True, metric='wbgt', threshold=36, reason='Synthetic UI fixture only', policy_source='test://frontend-fixture')]
        pipeline.environment_service.refresh_latest = lambda: envs
        original_assess = pipeline.risk.assess
        pipeline.risk.assess = lambda environments: original_assess(environments, as_of=NOW)
        prefs = Preferences()
        generic = pipeline.run(prefs)
        predictions = []
        def difficulty(routes, environments):
            for route in routes:
                value = 3 if route.route_id == 'west_coast' else 5 if route.route_id == 'marina_bay' else 4
                predictions.append(dict(route_id=route.route_id, generic_predicted_difficulty=3, personalized_predicted_difficulty=value, confidence='medium'))
            return {p['route_id']:p['personalized_predicted_difficulty'] for p in predictions}
        personal = pipeline.run(prefs, difficulty_provider=difficulty)
        output = {'fixture_kind': 'Synthetic UI observations and personal predictions; never real weather or user history',
                  'generic': generic.model_dump(mode='json'),
                  'personalized': {'run': personal.model_dump(mode='json'), 'target_difficulty': 3,
                                   'recommendations': rank_candidates(personal.recommendations, predictions, 3)}}
        (ROOT/'tests/fixtures/frontend_run.json').write_text(json.dumps(output, separators=(',', ':'))+'\n')


if __name__ == '__main__': build()
