"""Owner 5 extension: no invented health threshold or compound safety score."""
from outdoorwise.contracts.environment import EnvironmentRisk,utc_now
class UnavailableRiskAssessor:
    def assess(self,environments):
        return [EnvironmentRisk(route_id=e.route_id,assessed_at=utc_now(),
            reasons=['Risk module not connected. Official heat stress is displayed as source observation.']) for e in environments]
