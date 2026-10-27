"""Departure-only replay adapter; research inference and risk mathematics are read-only.

Observations may assess Now. Direct native forecast targets may assess exactly
that target, never an interval painted around it. Rain/wind held-value research
assumptions have no validated delayed target contract, so remain unavailable.
"""
from datetime import timedelta
from math import isfinite

from outdoorwise.contracts.environment import RouteEnvironment, timestamp
from outdoorwise.modules.risk import EnvironmentalRiskAssessor


def assess_departure(environment, observation_risk, native_forecast, config, origin, delay):
    departure = origin + timedelta(minutes=delay)
    evidence = {}
    if delay == 0:
        risk = observation_risk.model_dump(mode='json')
        for metric in environment.metrics:
            evidence[metric.metric] = dict(input_kind='historical_observation',
                value=metric.value, unit=metric.unit, source=metric.source,
                location_id=metric.location_id, observed_at=metric.observed_at,
                fetched_at=metric.fetched_at, forecast_origin=None, target_timestamp=None,
                method='historical_observation', reason=metric.reason)
        return dict(assessment_time=departure.isoformat(), assessment_type='historical_observation',
                    risk=risk, inputs=evidence, scope='departure_only')

    metrics = []
    accepted = set()
    for original in environment.metrics:
        # No future carry-forward of origin observations, including categorical
        # heat and PSI fallbacks. An explicit native forecast is required.
        metric = original.model_copy(update={'value': None, 'category_value': None,
                                             'state': 'missing', 'reason': 'No supported departure-target forecast.'})
        name = original.metric
        item = dict(input_kind='unavailable', value=None, unit=original.unit,
                    source=original.source, location_id=original.location_id,
                    observed_at=original.observed_at, fetched_at=original.fetched_at,
                    forecast_origin=None, target_timestamp=departure.isoformat(),
                    method='unavailable', reason='No supported departure-target forecast.')
        if name in {'rainfall', 'wind_speed'}:
            item['reason'] = 'Research held-value assumption has no validated delayed-target contract; not used as a future measurement.'
        if name in {'wbgt', 'pm25'}:
            series = native_forecast.get('metrics', {}).get(name, {})
            source = native_forecast.get('sources', {}).get(name)
            location = source.get('station_id') if isinstance(source, dict) else source
            candidates = [block for block in series.get('blocks', [])
                          if timestamp(block['valid_to']) == departure]
            item['reason'] = 'No exact native forecast target at departure; no interpolation or interval extension.'
            if len(candidates) == 1:
                block = candidates[0]
                model_origin = timestamp(series['model_origin'])
                horizon = (departure-model_origin).total_seconds()/60
                provenance = block.get('input_provenance', [])
                item.update(method=block['method'], forecast_origin=series['model_origin'],
                    native_value=block['value'], native_unit=series.get('unit'),
                    model_identifier=block.get('model_name'), model_version=block.get('model_version'),
                    input_provenance=provenance, horizon_min=horizon, native_interval={
                        'valid_from': block['valid_from'], 'valid_to': block['valid_to']})
                native_grid = (name == 'wbgt' and model_origin.minute % 15 == 0 and horizon in range(15, 181, 15)) or (
                    name == 'pm25' and model_origin.minute == 0 and horizon in {60, 120, 180})
                available = bool(provenance) and all(
                    timestamp(record['observed_at']) <= model_origin and timestamp(record['available_at']) <= model_origin
                    for record in provenance)
                matching_input = any(timestamp(record['observed_at']) == original.observed_at
                    and record.get('station_id', record.get('region')) == original.location_id for record in provenance)
                valid_model = block['method'] != 'frozen_experimental_linear' or (
                    block.get('model_version') not in {None, 'unavailable'} and block.get('training_cutoff') is not None
                    and timestamp(block['training_cutoff']) <= model_origin)
                methods = {'persistence'} if name == 'wbgt' else {'persistence', 'persistence_fallback', 'frozen_experimental_linear'}
                usable = (block['method'] in methods
                    and block['value'] is not None and isfinite(block['value'])
                    and series.get('unit') == original.unit and location == original.location_id
                    and model_origin <= origin and available and matching_input and native_grid and valid_model)
                if usable:
                    metric = original.model_copy(update={'value': block['value'], 'category_value': None,
                        'reason': 'Native forecast at exact departure; source timestamps refer to origin inputs.'})
                    accepted.add(name)
                    item.update(input_kind='forecast', value=block['value'], reason='Exact native departure target; not continuous run exposure.')
                else:
                    item['reason'] = 'Native target unavailable or incompatible: check method, unit, location, grid, model artifact and origin-time input availability.'
        evidence[name] = item
        metrics.append(metric)

    class DepartureAssessor(EnvironmentalRiskAssessor):
        def measurement(self, metric, as_of):
            # Validate forecast source observations at their forecast origin,
            # retaining original observed/fetched timestamps. Exact target and
            # input availability were checked above. All scoring curves, heat/
            # air fallbacks, required components and policy remain inherited.
            return super().measurement(metric, origin if metric and metric.metric in accepted else as_of)

    assessment = DepartureAssessor(config).assess([
        RouteEnvironment(route_id=environment.route_id, as_of=departure, metrics=metrics)], departure)[0]
    risk = assessment.model_dump(mode='json')
    risk.update(source='historical_departure_forecast_adapter', risk_assessment_mode='experimental_historical_forecast')
    risk['risk_warnings'] = [text for text in risk['risk_warnings'] if text != 'Current observations only; no future weather values are inferred.']
    risk['risk_warnings'].append('Exact-target experimental forecasts only; no claim of continuous run coverage.')
    return dict(assessment_time=departure.isoformat(), assessment_type='forecast_based',
                risk=risk, inputs=evidence, scope='departure_only')


def full_run_coverage(forecast):
    components = forecast['forecast_risk']['components']
    fractions = [item.get('coverage_fraction', 0) for item in components.values()]
    return dict(status='complete' if fractions and all(value == 1 for value in fractions) else
                'partial' if any(value > 0 for value in fractions) else 'unavailable',
                risk_score=forecast['forecast_risk']['risk_score'],
                component_coverage={name: item.get('coverage_fraction', 0) for name, item in components.items()},
                reason='Continuous run coverage is separate from native departure targets; unsupported exposure remains unknown.')
