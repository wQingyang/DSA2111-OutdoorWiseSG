from math import radians, sin, cos, atan2, sqrt
from .models import Coordinate
def distance_km(a: Coordinate, b: Coordinate) -> float:
    x,y = radians(b.lat-a.lat), radians(b.lon-a.lon)
    h=sin(x/2)**2+cos(radians(a.lat))*cos(radians(b.lat))*sin(y/2)**2
    return 6371*2*atan2(sqrt(max(0,h)), sqrt(max(0,1-h)))
