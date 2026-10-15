"""Additive risk contracts and validated engineering configuration."""
from math import isclose
from typing import Literal
from pydantic import Field, model_validator
from .core import Contract


class Curve(Contract):
    points: list[tuple[float, float]]

    @model_validator(mode='after')
    def validate_points(self):
        if len(self.points) < 2 or any(a[0] >= b[0] or a[1] > b[1] for a, b in zip(self.points, self.points[1:])):
            raise ValueError('Risk curves require increasing x and nondecreasing scores')
        if any(not 0 <= y <= 100 for _, y in self.points):
            raise ValueError('Curve scores must lie in 0..100')
        return self


class BlockingRule(Contract):
    enabled: bool = False
    metric: Literal['rainfall', 'wbgt', 'pm25', 'psi', 'wind_speed']
    threshold: float = Field(ge=0)
    policy_source: str = ''
    reason: str = ''
    allow_approximate_estimates: bool = False

    @model_validator(mode='after')
    def validate_support(self):
        if self.enabled and (not self.policy_source.strip() or not self.reason.strip()):
            raise ValueError('Enabled blocking rules require a policy source and reason')
        return self


def validate_weights(weights, expected):
    if set(weights) != expected or any(v < 0 for v in weights.values()) or not isclose(sum(weights.values()), 1, abs_tol=1e-9):
        raise ValueError('Weights must have registered keys, be nonnegative and sum to one')


class RiskConfig(Contract):
    weights: dict[str, float] = Field(default_factory=lambda: dict(rainfall=.35, heat=.35, air_quality=.25, wind=.05))
    rainfall: Curve = Field(default_factory=lambda: Curve(points=[(0, 0), (1, 20), (5, 60), (10, 100)]))
    wbgt: Curve = Field(default_factory=lambda: Curve(points=[(26, 0), (31, 50), (33, 80), (35, 100)]))
    pm25: Curve = Field(default_factory=lambda: Curve(points=[(0, 0), (55, 25), (150, 60), (250, 85), (350, 100)]))
    psi: Curve = Field(default_factory=lambda: Curve(points=[(0, 0), (50, 15), (100, 35), (200, 70), (300, 90), (400, 100)]))
    wind: Curve = Field(default_factory=lambda: Curve(points=[(8, 0), (20, 100)]))
    wind_scoring_enabled: bool = False
    heat_category_scores: dict[str, float] = Field(default_factory=lambda: {'Low': 20, 'Moderate': 60, 'High': 90})
    heat_category_thresholds: tuple[float, float] = (31, 33)
    spatial_bands_km: tuple[float, float, float] = (1, 3, 5)
    max_reliable_station_distance_km: float = Field(default=5, gt=0)
    allow_approximate_station_estimates: bool = True
    caution_score: float = Field(default=40, ge=0, le=100)
    high_score: float = Field(default=70, ge=0, le=100)
    blocking_rules: list[BlockingRule] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_config(self):
        validate_weights(self.weights, {'rainfall', 'heat', 'air_quality', 'wind'})
        scores = self.heat_category_scores
        if set(scores) != {'Low', 'Moderate', 'High'} or not 0 <= scores['Low'] <= scores['Moderate'] <= scores['High'] <= 100:
            raise ValueError('Heat category scores must increase within 0..100')
        if not 0 < self.spatial_bands_km[0] < self.spatial_bands_km[1] < self.spatial_bands_km[2]:
            raise ValueError('Spatial bands must be positive and increasing')
        if self.heat_category_thresholds[0] >= self.heat_category_thresholds[1] or self.caution_score > self.high_score:
            raise ValueError('Category thresholds must be increasing')
        return self


class RankingConfig(Contract):
    weights: dict[str, float] = Field(default_factory=lambda: dict(environment=.45, distance=.25, accessibility=.15, difficulty=.15))
    neutral_accessibility: float = Field(default=50, ge=0, le=100)
    distance_relative_tolerance: float = Field(default=.30, ge=0)
    access_penalty_per_km: float = Field(default=2, gt=0)

    @model_validator(mode='after')
    def validate_config(self):
        validate_weights(self.weights, {'environment', 'distance', 'accessibility', 'difficulty'})
        return self


class RiskComponent(Contract):
    score: float | None = Field(default=None, ge=0, le=100)
    metric: str | None = None
    freshness: Literal['fresh', 'stale', 'missing', 'unavailable_as_of'] = 'missing'
    spatial_quality: Literal['high', 'moderate', 'low', 'very_low', 'regional', 'unknown'] = 'unknown'
    station_distance_km: float | None = None
    aggregation_window: str | None = None
    category: str | None = None
    warnings: list[str] = Field(default_factory=list)
    estimate_status: Literal['supported', 'approximate', 'unavailable'] = 'unavailable'


class RiskDataQuality(Contract):
    completeness: float = Field(default=0, ge=0, le=1)
    reliable_components: int = 0
    scored_components: int = 0
    required_components: int = 4
    spatial_quality: str = 'unknown'
    observation_freshness: str = 'missing'
    simulated: bool = False
    confidence: Literal['high', 'moderate', 'low', 'very_low', 'unknown'] = 'unknown'


def ranking_sort_key(eligibility, weighted_score, fallback_score, base_rank, route_id):
    """Blocks last, complete weighted assessments together, then unknown fallback.

    Confidence/caution labels do not impose a hidden lexicographic preference.
    Weighted and fallback scores are never compared on the same numeric scale.
    """
    return (eligibility == 'blocked', weighted_score is None,
            -(weighted_score if weighted_score is not None else fallback_score),
            base_rank, route_id)
