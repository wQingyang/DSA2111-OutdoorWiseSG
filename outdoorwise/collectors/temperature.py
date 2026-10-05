from .base import APICollector,parse_station
class TemperatureCollector(APICollector):
    source='nea_air_temperature'
    def parse(self,payload,fetched_at):
        return parse_station(payload,fetched_at,self.source,'air_temperature','deg C','DBT 1M F',lambda x:x)
