import zipfile
import io
import shapefile
from pathlib import Path

out_dir = Path("sample_data")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Generate sample_survey.kml (mixed geometry: Polygon, LineString, Point)
kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Bengaluru Solar Farm Survey</name>
    <description>Drone photogrammetry boundary and utility survey</description>
    
    <Placemark>
      <name>Solar Array Plot A</name>
      <description>Perimeter boundary of primary solar panel deployment</description>
      <ExtendedData>
        <Data name="zone_type"><value>Industrial</value></Data>
        <Data name="capacity_mw"><value>25.5</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5850,12.9650,0
              77.5890,12.9650,0
              77.5890,12.9690,0
              77.5850,12.9690,0
              77.5850,12.9650,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <Placemark>
      <name>HV Transmission Corridor</name>
      <description>Power transmission line connecting substation to grid</description>
      <ExtendedData>
        <Data name="voltage_kv"><value>66</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5850,12.9650,0
          77.5900,12.9700,0
          77.5950,12.9750,0
        </coordinates>
      </LineString>
    </Placemark>

    <Placemark>
      <name>GCP Base Station 01</name>
      <description>High precision RTK GPS reference station</description>
      <Point>
        <coordinates>77.5870,12.9670,920</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""

with open(out_dir / "sample_survey.kml", "w", encoding="utf-8") as f:
    f.write(kml_content)
print("Created sample_data/sample_survey.kml")

# 2. Generate sample_shapes.zip (Shapefile containing multiple Polygon features)
shp_io = io.BytesIO()
shx_io = io.BytesIO()
dbf_io = io.BytesIO()

w = shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON)
w.field("NAME", "C", size=50)
w.field("TYPE", "C", size=20)
w.field("STATUS", "C", size=20)

# Feature 1: Sector Alpha Polygon
w.poly([
    [[77.600, 13.000], [77.605, 13.000], [77.605, 13.005], [77.600, 13.005], [77.600, 13.000]]
])
w.record(NAME="Survey Sector 1", TYPE="Polygon", STATUS="Active")

# Feature 2: Water Reservoir Polygon
w.poly([
    [[77.610, 13.010], [77.614, 13.010], [77.614, 13.014], [77.610, 13.014], [77.610, 13.010]]
])
w.record(NAME="Reservoir Alpha", TYPE="Polygon", STATUS="Planned")

# Feature 3: Infrastructure Facility Polygon
w.poly([
    [[77.620, 13.020], [77.625, 13.020], [77.623, 13.024], [77.618, 13.023], [77.620, 13.020]]
])
w.record(NAME="Substation Yard", TYPE="Polygon", STATUS="Operational")

w.close()

# WGS84 WKT projection string for .prj
wgs84_prj = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'

zip_path = out_dir / "sample_shapes.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("survey_polygons.shp", shp_io.getvalue())
    z.writestr("survey_polygons.shx", shx_io.getvalue())
    z.writestr("survey_polygons.dbf", dbf_io.getvalue())
    z.writestr("survey_polygons.prj", wgs84_prj)

print(f"Created {zip_path} with .shp, .shx, .dbf, .prj files!")
