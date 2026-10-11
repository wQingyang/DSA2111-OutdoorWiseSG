from datetime import datetime, timezone
import xml.etree.ElementTree as ET

class RouteExportService:
    def render_gpx(self, route):
        ns="http://www.topografix.com/GPX/1/1"
        root=ET.Element("gpx",{"version":"1.1","creator":"OutdoorWise SG","xmlns":ns,"xmlns:xsi":"http://www.w3.org/2001/XMLSchema-instance","xsi:schemaLocation":f"{ns} http://www.topografix.com/GPX/1/1/gpx.xsd"})
        metadata=ET.SubElement(root,"metadata"); ET.SubElement(metadata,"name").text=route.name; ET.SubElement(metadata,"time").text=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
        trk=ET.SubElement(root,"trk"); ET.SubElement(trk,"name").text=route.name; seg=ET.SubElement(trk,"trkseg")
        for lon,lat in route.geometry.coordinates: ET.SubElement(seg,"trkpt",{"lat":str(lat),"lon":str(lon)})
        return ET.tostring(root,encoding="utf-8",xml_declaration=True)
