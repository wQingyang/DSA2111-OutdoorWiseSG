from .base import APICollector,parse_station
class HumidityCollector(APICollector):
    source='nea_relative_humidity'
    def parse(self,payload,fetched_at):
        return parse_station(payload,fetched_at,self.source,'relative_humidity','percentage','RH 1M F',lambda x:x)
