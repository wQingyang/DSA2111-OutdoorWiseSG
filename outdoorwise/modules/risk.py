"""Observation-based engineering risk; no forecasts or medical safety guarantees."""
from math import isfinite

from outdoorwise.contracts.environment import EnvironmentRisk, METRIC_SPECS, utc_now
from outdoorwise.contracts.risk import RiskComponent, RiskDataQuality
from .risk_policy import RiskPolicy


def normalize(value, curve):
    """Clamped piecewise-linear interpolation. Missing remains unknown."""
    if value is None or not isfinite(value):
        return None
    points = curve.points
    if value <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)
    return points[-1][1]


class EnvironmentalRiskAssessor:
    def __init__(self, config):
        self.config = config
        self.policy = RiskPolicy(config.risk)

    def measurement(self, metric, as_of):
        """Recheck timestamps and Mapping V1 coverage, never persisted state."""
        if metric is None:
            return RiskComponent(warnings=['Observation missing.'])
        cfg = self.config.risk
        unit, window, source = METRIC_SPECS[metric.metric]
        component = RiskComponent(metric=metric.metric, aggregation_window=metric.aggregation_window,
                                  station_distance_km=metric.station_distance_km)
        value = metric.category_value if metric.metric == 'heat_stress_level' else metric.value
        if value is None or (isinstance(value, (int, float)) and not isfinite(value)):
            component.warnings.append('Observation missing.')
            return component
        if (metric.source, metric.unit, metric.aggregation_window) != (source, unit, window):
            component.warnings.append('Source/unit/aggregation contract mismatch.')
            return component
        times = [metric.observed_at, metric.fetched_at, metric.source_updated_at]
        if metric.observed_at is None or metric.fetched_at is None:
            component.warnings.append('Observation availability timestamps missing.')
            return component
        if any(t is not None and t > as_of for t in times):
            component.freshness = 'unavailable_as_of'
            component.warnings.append('Observation was not available at evaluation time.')
            return component
        age = (as_of - metric.observed_at).total_seconds()
        component.freshness = 'fresh' if age <= self.config.sources[source].stale_after_seconds else 'stale'
        along_route = metric.match_method == 'along_route_sampling_500m_v1'
        if along_route:
            component.warnings.append('Conservative aggregation of along-route station samples; regional pollution uses nearest centroids, without polygon containment.')
            if not metric.sample_count or metric.matched_sample_count != metric.sample_count:
                component.warnings.append('Incomplete along-route sample coverage; environmental component unavailable.')
                return component
        if metric.metric in {'pm25', 'psi'}:
            if metric.match_method in {'configured_source_region_v1', 'along_route_sampling_500m_v1'} and metric.location_id:
                component.spatial_quality = 'regional'
                component.warnings.append('Configured regional measurement, not route-specific pollution.')
        elif metric.match_method in {'nearest_available_station_start_point_v1', 'along_route_sampling_500m_v1'} and metric.location_id:
            distance = metric.station_distance_km
            if distance is not None and isfinite(distance) and distance >= 0:
                bands = cfg.spatial_bands_km
                component.spatial_quality = next((name for limit, name in zip(bands, ['high', 'moderate', 'low']) if distance <= limit), 'very_low')
        if component.freshness != 'fresh':
            component.warnings.append('Observation exceeds configured freshness threshold.')
        reliable_spatial = component.spatial_quality == 'regional' or (
            component.spatial_quality != 'unknown' and metric.station_distance_km <= min(cfg.max_reliable_station_distance_km, self.config.matching.station_max_distance_km))
        approximate_spatial = (cfg.allow_approximate_station_estimates
                               and component.spatial_quality not in {'unknown', 'regional'}
                               and not reliable_spatial
                               and metric.station_distance_km <= self.config.matching.station_max_distance_km)
        if approximate_spatial:
            component.warnings.append('Distant-station approximate estimate with very low spatial confidence; not a measurement along this route.')
        elif not reliable_spatial:
            component.warnings.append('Insufficient spatial representativeness for scoring.')
        if metric.source_kind == 'demo':
            component.warnings.append('Synthetic demo observation, not live evidence.')
        if component.freshness == 'fresh' and (reliable_spatial or approximate_spatial):
            component.score = 0  # Marker of usable input; component scoring replaces it below.
            component.estimate_status = 'supported' if reliable_spatial else 'approximate'
        return component

    def assess(self, environments, as_of=None):
        as_of = as_of or utc_now()
        if as_of.tzinfo is None:
            raise ValueError('Risk evaluation time must be timezone-aware')
        return [self._assess(environment, as_of) for environment in environments]

    def _assess(self, environment, as_of):
        cfg = self.config.risk
        metrics = {m.metric: m for m in environment.metrics}
        inputs = {name: self.measurement(metrics.get(name), as_of) for name in
                  ['rainfall', 'wbgt', 'heat_stress_level', 'pm25', 'psi', 'wind_speed']}
        components = {}
        rain = inputs['rainfall'].model_copy(deep=True)
        if rain.score is not None:
            rain.score = normalize(metrics['rainfall'].value, cfg.rainfall)
        rain.warnings.append('5-minute station accumulation; zero does not establish a dry entire route or future dry weather.')
        components['rainfall'] = rain
        heat_metric = 'wbgt' if inputs['wbgt'].score is not None else 'heat_stress_level'
        if inputs['heat_stress_level'].score is None and metrics.get('wbgt') and metrics['wbgt'].value is not None:
            heat_metric = 'wbgt'
        heat = inputs[heat_metric].model_copy(deep=True)
        if heat.score is not None:
            if heat_metric == 'wbgt':
                value = metrics['wbgt'].value
                heat.score = normalize(value, cfg.wbgt)
                lower, upper = cfg.heat_category_thresholds
                heat.category = 'Low' if value < lower else 'Moderate' if value < upper else 'High'
                official = metrics.get('heat_stress_level')
                if official and official.category_value and official.category_value != heat.category:
                    heat.warnings.append('Official category differs from numeric WBGT category; numeric WBGT is used once.')
            else:
                heat.category = metrics['heat_stress_level'].category_value
                heat.score = cfg.heat_category_scores.get(heat.category)
                heat.warnings.append('Numeric WBGT unavailable; using categorical heat fallback only.')
        components['heat'] = heat
        air_metric = 'pm25' if inputs['pm25'].score is not None else 'psi'
        if inputs['psi'].score is None and metrics.get('pm25') and metrics['pm25'].value is not None:
            air_metric = 'pm25'
        air = inputs[air_metric].model_copy(deep=True)
        if air.score is not None:
            air.score = normalize(metrics[air_metric].value, getattr(cfg, air_metric))
        air.warnings.append('Uses 1-hour PM2.5 only when usable; otherwise 24-hour PSI only. These are not instantaneous measurements.')
        components['air_quality'] = air
        wind = inputs['wind_speed'].model_copy(deep=True)
        if wind.score is not None:
            wind.score = normalize(metrics['wind_speed'].value, cfg.wind) if cfg.wind_scoring_enabled else 0
        wind.warnings.append('Wind scoring neutral by default; no headwind/tailwind or gust inference.')
        components['wind'] = wind
        reliable = sum(c.score is not None for c in components.values())
        score = sum(cfg.weights[name] * c.score for name, c in components.items()) if reliable == 4 else None
        score = round(score, 2) if score is not None else None
        simulated = any(metrics[c.metric].source_kind == 'demo' for c in components.values() if c.metric in metrics)
        spatial = [c.spatial_quality for c in components.values()]
        worst = next((q for q in ['unknown', 'very_low', 'low', 'moderate', 'regional', 'high'] if q in spatial), 'unknown')
        freshness = {c.freshness for c in components.values()}
        approximate = any(c.estimate_status == 'approximate' for c in components.values())
        confidence = 'unknown' if score is None else 'very_low' if simulated or approximate else 'moderate' if worst == 'regional' else worst
        if score is not None and any(c.metric in {'psi', 'heat_stress_level'} for c in components.values()) and confidence == 'high':
            confidence = 'moderate'
        quality = RiskDataQuality(completeness=reliable / 4, scored_components=reliable,
                                  reliable_components=sum(c.score is not None and c.estimate_status == 'supported' for c in components.values()),
                                  confidence=confidence,
                                  spatial_quality=worst, observation_freshness=next(iter(freshness)) if len(freshness) == 1 else 'mixed', simulated=simulated)
        warnings = ['Provisional engineering score, not a medical or safety guarantee.',
                    'Mapping V1 uses route start-point stations and configured regions, not measurements along the entire route.',
                    'Current observations only; no future weather values are inferred.']
        if any(m.match_method == 'along_route_sampling_500m_v1' for m in environment.metrics):
            warnings[1] = 'Dynamic routes use along-route samples with conservative component maxima; station distances refer to samples, not the route start. Regional matching uses nearest centroids.'
        warnings += [f'{name}: {warning}' for name, c in components.items() for warning in c.warnings]
        risk = EnvironmentRisk(route_id=environment.route_id, assessed_at=as_of,
                               status=('demo' if simulated else 'available') if score is not None else 'unavailable',
                               source='observation_risk_v1', risk_score=score,
                               risk_level='unknown' if score is None else 'high' if score >= cfg.high_score else 'elevated' if score >= cfg.caution_score else 'low',
                               risk_components=components, risk_status='complete' if score is not None else 'incomplete',
                               risk_data_quality=quality, risk_warnings=warnings,
                               reasons=[f'{name}: {c.score:.2f}/100 from {c.metric}.' if c.score is not None else f'{name}: unknown; no overall score.' for name, c in components.items()])
        self.policy.apply(risk, metrics, inputs)
        return risk


class UnavailableRiskAssessor:
    """Retained for existing integrations that explicitly disable assessment."""
    def assess(self, environments):
        return [EnvironmentRisk(route_id=e.route_id, assessed_at=utc_now(),
                                reasons=['Risk module not connected.']) for e in environments]
