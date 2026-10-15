"""Location wiring through the existing APIs/calculator; temporary data only."""
import shutil

import pytest
from fastapi.testclient import TestClient

from outdoorwise.api.app import create_app
from outdoorwise.config import ROOT, Settings
from outdoorwise.contracts.core import Coordinate
from outdoorwise.contracts.geo import distance_km


@pytest.fixture
def app(tmp_path):
    shutil.copytree(ROOT/'data/catalog', tmp_path/'catalog')
    # Live mode with empty temporary storage never triggers collection on startup.
    return create_app(Settings(data_root=tmp_path, data_mode='live'))


def run_response(client, endpoint, payload):
    response = client.post(endpoint, json=payload)
    assert response.status_code == 200
    data = response.json()
    return data['run'] if endpoint.startswith('/api/me/') else data, data


@pytest.mark.parametrize('personal', [False, True])
def test_coordinates_access_calculation_filter_and_clear(app, personal):
    with TestClient(app) as client:
        endpoint = '/api/me/recommendations' if personal else '/api/recommendations'
        if personal:
            assert client.post('/api/auth/register', json={'username': 'location_runner', 'password': 'test-password'}).status_code == 201
        routes = app.state.pipeline.repository.load_routes()
        assert len(routes) == 12
        marina = next(r for r in routes if r.route_id == 'marina_bay')
        lon, lat = marina.geometry.coordinates[0]
        point = {'lon': lon, 'lat': lat}
        payload = {'location': point, 'max_access_distance_km': 100, 'target_difficulty': 3}
        result, outer = run_response(client, endpoint, payload)
        assert result['preferences']['location'] == point
        assert result['preferences']['max_access_distance_km'] == 100
        assert len(result['recommendations']) == 12
        for rec in result['recommendations']:
            route = next(r for r in routes if r.route_id == rec['route_id'])
            start_lon, start_lat = route.geometry.coordinates[0]
            expected = distance_km(Coordinate(**point), Coordinate(lon=start_lon, lat=start_lat))
            assert rec['access_distance_km'] == round(expected, 3)
        assert next(r for r in result['recommendations'] if r['route_id'] == 'marina_bay')['access_distance_km'] == 0
        repeat, repeat_outer = run_response(client, endpoint, payload)
        assert [(r['route_id'], r['access_distance_km']) for r in repeat['recommendations']] == [(r['route_id'], r['access_distance_km']) for r in result['recommendations']]
        if personal:
            assert [r['route_id'] for r in outer['recommendations']] == [r['route_id'] for r in result['recommendations']]
            assert [r['route_id'] for r in repeat_outer['recommendations']] == [r['route_id'] for r in result['recommendations']]
        # One metre at the exact catalog start keeps only the matching route.
        strict, strict_outer = run_response(client, endpoint, {**payload, 'max_access_distance_km': .001})
        assert [r['route_id'] for r in strict['recommendations']] == ['marina_bay']
        assert strict['preferences']['max_access_distance_km'] == .001
        if personal:
            assert [r['route_id'] for r in strict_outer['recommendations']] == ['marina_bay']
        # No candidate meets one metre from this approximate NUS preset.
        empty, empty_outer = run_response(client, endpoint, {**payload, 'location': {'lon': 103.776, 'lat': 1.296}, 'max_access_distance_km': .001})
        assert empty['recommendations'] == []
        assert empty['preferences']['location'] == {'lon': 103.776, 'lat': 1.296}
        assert empty['preferences']['max_access_distance_km'] == .001
        if personal: assert empty_outer['recommendations'] == []
        cleared, _ = run_response(client, endpoint, {'location': None, 'max_access_distance_km': None, 'target_difficulty': 3})
        assert len(cleared['recommendations']) == 12
        assert all(r['access_distance_km'] is None for r in cleared['recommendations'])


@pytest.mark.parametrize('point', [{'lon': 181, 'lat': 1.3}, {'lon': 103.8, 'lat': 91}, {'lon': 1.3, 'lat': 103.8}])
def test_invalid_or_swapped_coordinates_rejected(app, point):
    with TestClient(app) as client:
        assert client.post('/api/recommendations', json={'location': point}).status_code == 422
