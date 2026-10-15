"""Recorded UI fixture stays compatible with actual typed recommendation output."""
import json
from outdoorwise.config import ROOT
from outdoorwise.contracts.models import Run


def test_synthetic_frontend_fixture_matches_response_contracts():
    fixture = json.loads((ROOT/'tests/fixtures/frontend_run.json').read_text())
    assert fixture['fixture_kind'].startswith('Synthetic')
    generic = Run.model_validate(fixture['generic'])
    personal = Run.model_validate(fixture['personalized']['run'])
    assert len(generic.routes) == len(personal.routes) == 12
    wrapper = fixture['personalized']['recommendations']
    assert [r['route_id'] for r in wrapper] == [r.route_id for r in personal.recommendations]
    assert all(r['personalized_rank'] == r['final_rank'] == i for i, r in enumerate(wrapper, 1))
    assert all(len(e.metrics) == 10 for e in generic.environment)
    assert any(r.eligibility == 'blocked' for r in generic.risks)
