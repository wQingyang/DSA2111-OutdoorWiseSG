from .base import APICollector,parse_station
class WindDirectionCollector(APICollector):
    source='nea_wind_direction'
    def parse(self,payload,fetched_at):
        return parse_station(payload,fetched_at,self.source,'wind_direction','degrees','Wind Dir AVG (S) 10M M1M',lambda x:x)
