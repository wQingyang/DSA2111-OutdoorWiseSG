from .base import APICollector,parse_station
class WindSpeedCollector(APICollector):
    source='nea_wind_speed'
    def parse(self,payload,fetched_at):
        return parse_station(payload,fetched_at,self.source,'wind_speed','knots','Wind Speed AVG(S)10M M1M',lambda x:x*1852/3600)
