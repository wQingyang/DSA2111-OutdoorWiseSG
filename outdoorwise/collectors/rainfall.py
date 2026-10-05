from .base import APICollector,parse_station
class RainfallCollector(APICollector):
    source='nea_rainfall'
    def parse(self,payload,fetched_at):
        return parse_station(payload,fetched_at,self.source,'rainfall','mm','TB1 Rainfall 5 Minute Total F',lambda x:x)
