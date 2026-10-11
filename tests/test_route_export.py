from fastapi.testclient import TestClient
from outdoorwise.api.app import create_app
from outdoorwise.config import Settings, ROOT
import xml.etree.ElementTree as ET

def test_export_does_not_change_route_api(tmp_path):
    import shutil
    shutil.copytree(ROOT/"data/catalog",tmp_path/"catalog")
    with TestClient(create_app(Settings(data_root=tmp_path,data_mode="demo"))) as client:
        before=client.get("/api/routes").json(); client.get("/api/routes/marina_bay/export.gpx"); after=client.get("/api/routes").json()
        assert before==after

def test_gpx_export_preserves_geometry_without_elevation(tmp_path):
    import shutil, json
    shutil.copytree(ROOT/"data/catalog",tmp_path/"catalog")
    source=json.loads((tmp_path/"catalog/marina_bay.geojson").read_text())["geometry"]["coordinates"]
    with TestClient(create_app(Settings(data_root=tmp_path,data_mode="demo"))) as client:
        response=client.get("/api/routes/marina_bay/export.gpx")
        assert response.status_code==200 and response.headers["content-type"].startswith("application/gpx+xml")
        assert "outdoorwise_marina_bay_" in response.headers["content-disposition"]
        root=ET.fromstring(response.content); ns={"g":"http://www.topografix.com/GPX/1/1"}
        assert root.find("g:trk/g:name",ns).text == "Marina Bay waterfront loop"
        points=root.findall("g:trk/g:trkseg/g:trkpt",ns)
        assert len(points)==len(source)
        assert float(points[0].attrib["lon"])==source[0][0] and float(points[0].attrib["lat"])==source[0][1]
        assert float(points[-1].attrib["lon"])==source[-1][0] and float(points[-1].attrib["lat"])==source[-1][1]
        assert all("ele" not in point.attrib for point in points)
        assert client.get("/api/routes/unknown/export.gpx").status_code==404
