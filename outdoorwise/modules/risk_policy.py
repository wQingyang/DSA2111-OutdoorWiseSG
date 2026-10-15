"""Eligibility policy is separate from numeric scoring and personal preference."""
class RiskPolicy:
    def __init__(self, config):
        self.config = config

    def apply(self, risk, metrics, inputs):
        for rule in self.config.blocking_rules:
            component = inputs[rule.metric]
            metric = metrics.get(rule.metric)
            if rule.enabled and component.score is not None and metric.value >= rule.threshold:
                if component.estimate_status == 'approximate' and not rule.allow_approximate_estimates:
                    risk.risk_warnings.append('Configured blocking threshold met only by an approximate station estimate; rule does not authorize approximate evidence. Caution retained.')
                    continue
                risk.eligibility = 'blocked'
                risk.risk_warnings.append(f'Blocked by configured policy: {rule.reason} ({rule.policy_source}).')
                return
        if risk.risk_score is None:
            risk.eligibility = 'unknown'
        elif (risk.risk_score >= self.config.caution_score or risk.risk_data_quality.simulated
              or any(c.spatial_quality in {'low', 'very_low'} or c.metric in {'psi', 'heat_stress_level'}
                     or (c.score is not None and c.score >= self.config.high_score)
                     for c in risk.risk_components.values())):
            risk.eligibility = 'caution'
        else:
            risk.eligibility = 'eligible'
