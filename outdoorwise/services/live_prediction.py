"""Supplementary persistence estimates from an availability-filtered live snapshot.

No research script, training call, historical dataset or external API is used here.
The short horizons are engineering limits, not claims of validated forecast skill.
"""
from datetime import timedelta
from math import isfinite
from typing import Literal

from pydantic import AwareDatetime, Field

from outdoorwise.contracts.core import Contract
from outdoorwise.contracts.environment import utc_now
from .route_environment import RouteEnvironmentService

# Conservative, explicitly unvalidated limits; never extend to an arbitrary run.
PERSISTENCE_HORIZONS = {'rainfall': 5, 'wind_speed': 10, 'wbgt': 15, 'pm25': 60}


class LiveMetricForecast(Contract):
    metric: str
    issue_time: AwareDatetime
    valid_from: AwareDatetime
    valid_to: AwareDatetime
    model_name: str = 'observation_persistence'
    model_version: str = 'persistence-v1'
    horizon_min: int
    value: float | None = None
    unit: str
    method: Literal['trained_model', 'persistence', 'unavailable']
    status: Literal['experimental'] = 'experimental'
    validated: bool = False
    input_observation_timestamps: list[AwareDatetime] = Field(default_factory=list)
    first_fetched_at: AwareDatetime | None = None
    fetched_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    revision: int | None = None
    source: str
    source_location_id: str | None = None
    freshness: str
    spatial_quality: str
    match_method: str
    station_distance_km: float | None = None
    covers_entire_run: bool
    covered_minutes: float = Field(ge=0)
    missing_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LivePredictionService:
    def __init__(self, repository, config, mode):
        self.repository = repository
        self.config = config
        self.mode = mode

    def predict(self, route_id, start_delay_min=0, duration_min=30, issue_time=None):
        issue = issue_time or utc_now()
        if issue.tzinfo is None:
            raise ValueError('Forecast issue time must be timezone-aware.')
        if start_delay_min < 0 or duration_min <= 0 or start_delay_min + duration_min > 180:
            raise ValueError('Requested window must be positive and within 180 minutes.')
        snapshot = self.repository.environment_snapshot('live', issue) if self.mode == 'live' else ([], [], [])
        routes = self.repository.load_routes()
        if route_id not in {route.route_id for route in routes}:
            raise KeyError(route_id)

        class SnapshotReader:
            def load_routes(self): return routes
            def environment_snapshot(self, source_kind, as_of): return snapshot

        environment = RouteEnvironmentService(SnapshotReader(), self.config, 'live').get_route_environment(route_id, issue)
        start = issue + timedelta(minutes=start_delay_min)
        end = start + timedelta(minutes=duration_min)
        output = []
        for metric in environment.metrics:
            if metric.metric not in PERSISTENCE_HORIZONS:
                continue
            horizon = PERSISTENCE_HORIZONS[metric.metric]
            valid_to = issue + timedelta(minutes=horizon)
            observation = next((o for o in snapshot[1] if o.source == metric.source
                and o.location_id == metric.location_id and o.metric == metric.metric
                and o.observed_at == metric.observed_at and o.revision == metric.revision), None)
            reasons = []
            if self.mode != 'live': reasons.append('Live inference disabled in demo mode.')
            if metric.state != 'fresh': reasons.append('Fresh observation required; input is ' + metric.state + '.')
            if metric.value is None or not isfinite(metric.value): reasons.append('Numeric input unavailable.')
            if observation is None: reasons.append('Availability-filtered observation provenance unavailable.')
            usable = not reasons
            covered = max(0, (min(end, valid_to) - max(start, issue)).total_seconds() / 60) if usable else 0
            warnings = ['Unvalidated persistence assumption: the latest value remains constant.',
                'Supplementary evidence only; does not affect recommendation ranking.',
                'Rainfall is 5-minute accumulation, not rain probability or a future run total.'] if metric.metric == 'rainfall' else [
                'Unvalidated persistence assumption: the latest value remains constant.',
                'Supplementary evidence only; does not affect recommendation ranking.']
            if covered < duration_min: warnings.append('Estimate does not cover the entire requested run.')
            regional = metric.metric == 'pm25'
            spatial = 'regional' if regional and metric.location_id else 'unknown'
            if not regional and metric.station_distance_km is not None and metric.location_id:
                spatial = next((quality for limit, quality in zip(self.config.risk.spatial_bands_km,
                    ['high', 'moderate', 'low']) if metric.station_distance_km <= limit), 'very_low')
                if metric.station_distance_km > self.config.risk.max_reliable_station_distance_km:
                    warnings.append('Distant station estimate with very low spatial confidence, not a route measurement.')
            warnings.append('Configured regional pollution, not route-specific.' if regional else 'Station matched to route start; not an along-route forecast.')
            if metric.reason: warnings.append(metric.reason)
            output.append(LiveMetricForecast(metric=metric.metric, issue_time=issue, valid_from=issue,
                valid_to=valid_to, horizon_min=horizon, value=metric.value if usable else None,
                unit=metric.unit, method='persistence' if usable else 'unavailable',
                input_observation_timestamps=[observation.observed_at] if observation else [],
                first_fetched_at=(observation.first_fetched_at or observation.fetched_at) if observation else None,
                fetched_at=observation.fetched_at if observation else None,
                source_updated_at=observation.source_updated_at if observation else None,
                revision=observation.revision if observation else None,
                source=metric.source, source_location_id=metric.location_id, freshness=metric.state,
                spatial_quality=spatial,
                match_method=metric.match_method, station_distance_km=metric.station_distance_km,
                covers_entire_run=usable and covered >= duration_min, covered_minutes=covered,
                missing_reasons=reasons, warnings=warnings))
        return dict(mode='live_supplementary_forecast', issue_time=issue, route_id=route_id,
            run_start=start, run_end=end, metrics=output, ranking_uses='current_observation',
            warnings=['No validated live trained model is activated. Rain probability is unavailable.',
                'PM2.5 frozen backtest coefficients remain historical-only pending evaluation evidence.'])
