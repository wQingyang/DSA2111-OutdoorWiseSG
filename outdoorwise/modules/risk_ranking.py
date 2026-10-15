"""Score existing candidates without changing their geometry or access filtering."""
from outdoorwise.contracts.risk import ranking_sort_key


def recommendation_sort_key(rec, fallback_score=None):
    # Weighted and fallback scores are never compared across assessment groups.
    return ranking_sort_key(rec.eligibility, rec.recommendation_score,
                            rec.score if fallback_score is None else fallback_score,
                            rec.original_base_rank or 1, rec.route_id)


class RiskAwareRanking:
    def __init__(self, config):
        self.config = config

    def rank(self, candidates, risks, routes, preferences, difficulties, personalized=False):
        risk_by_id = {r.route_id: r for r in risks}
        route_by_id = {r.route_id: r for r in routes}
        output = []
        for base_rank, candidate in enumerate(candidates, 1):
            rec = candidate.model_copy(deep=True)
            rec.original_base_rank = base_rank
            risk = risk_by_id[rec.route_id]
            rec.risk_score = risk.risk_score
            rec.risk_level = risk.risk_level
            rec.risk_status = risk.risk_status
            rec.risk_assessment_mode = risk.risk_assessment_mode
            rec.risk_confidence = risk.risk_data_quality.confidence
            rec.eligibility = risk.eligibility
            relative = abs(route_by_id[rec.route_id].distance_km - preferences.target_distance_km) / preferences.target_distance_km
            rec.relative_distance_difference = round(relative, 6)
            if relative > self.config.distance_relative_tolerance:
                rec.distance_match_warning = f'Route differs from target by {relative:.0%}; it is not a close distance match. Geometry is unchanged.'
            reasons = ['Risk uses current observations, not the requested forecast window.']
            reasons.append('Complete eligible/caution assessments share weighted ordering; confidence is disclosed separately and explicit blocks take precedence.')
            if rec.risk_confidence in {'low', 'very_low'}:
                reasons.append(f'Environmental estimate has {rec.risk_confidence} confidence; inspect spatial warnings before choosing a route.')
            if rec.distance_match_warning:
                reasons.append(rec.distance_match_warning)
            if rec.access_distance_km is None:
                reasons.append(f'Starting location absent; accessibility uses the same neutral {self.config.neutral_accessibility:g}/100 for all candidates.')
            if risk.risk_score is None or risk.eligibility == 'blocked':
                rec.recommendation_score = None
                rec.recommendation_components = {}
                rec.ranking_method = 'blocked' if risk.eligibility == 'blocked' else 'legacy_non_environmental'
                reasons.append('Blocked by explicit policy; discovery only, not a recommended run.' if risk.eligibility == 'blocked' else 'Environmental assessment unknown; fallback uses existing distance/access/available forecast baseline, not environmental suitability.')
                if personalized and risk.eligibility != 'blocked':
                    rec.ranking_method = 'personalized_non_environmental'
                    reasons.append('Unknown-risk fallback is reordered by personal difficulty mismatch, with original baseline rank resolving ties.')
            else:
                # Relative normalization corrects the old absolute-distance bias for short targets.
                components = {'environment': 100 - risk.risk_score,
                              'distance': 100 * max(0, 1 - relative),
                              'accessibility': self.config.neutral_accessibility if rec.access_distance_km is None else max(0, 100 - self.config.access_penalty_per_km * rec.access_distance_km),
                              'difficulty': 100 * max(0, 1 - abs(difficulties[rec.route_id] - preferences.target_difficulty) / 4)}
                rec.recommendation_score = round(sum(self.config.weights[k] * v for k, v in components.items()), 2)
                rec.recommendation_components = {k: round(v, 2) for k, v in components.items()}
                rec.ranking_method = 'risk_weighted_v1'
                reasons.append('Weighted environmental suitability, relative distance match, accessibility and difficulty match; provisional engineering weights.')
            rec.ranking_reasons = reasons
            rec.reasons.extend(reasons)
            output.append(rec)
        def key(rec):
            fallback = -abs(difficulties[rec.route_id] - preferences.target_difficulty) if personalized else rec.score
            return recommendation_sort_key(rec, fallback)
        ranked = sorted(output, key=key)
        for position, rec in enumerate(ranked, 1):
            rec.final_rank = position
        return ranked
