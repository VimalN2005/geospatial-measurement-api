import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_DIR = Path(__file__).parent.parent / "sample_data"

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "documentation" in data

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_upload_kml():
    kml_file = SAMPLE_DIR / "sample_survey.kml"
    assert kml_file.exists()

    with open(kml_file, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_survey.kml", f, "application/vnd.google-earth.kml+xml")}
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_survey.kml"
    assert data["file_type"] == "KML"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"

    file_id = data["id"]

    # 1. Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["filename"] == "sample_survey.kml"
    assert info_data["feature_count"] == 3
    assert info_data["status"] == "COMPLETED"

    # 2. Test GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["file_id"] == file_id
    assert "EPSG:32643" in meas_data["projected_crs"]  # UTM zone 43N for Bengaluru (lon 77.58, lat 12.96)
    assert len(meas_data["features"]) == 3

    # Check Polygon feature
    polygon_f = next(f for f in meas_data["features"] if f["geometry_type"] == "Polygon")
    assert polygon_f["measurement_type"] == "area"
    assert polygon_f["measurements"]["area_sq_meters"] > 0
    assert polygon_f["measurements"]["area_hectares"] > 0

    # Check LineString feature
    line_f = next(f for f in meas_data["features"] if f["geometry_type"] == "LineString")
    assert line_f["measurement_type"] == "length"
    assert line_f["measurements"]["length_meters"] > 0
    assert line_f["measurements"]["length_km"] > 0

    # Check Point feature
    point_f = next(f for f in meas_data["features"] if f["geometry_type"] == "Point")
    assert point_f["measurement_type"] == "none"

    # 3. Test GET /api/files/{id}/features/ (GeoJSON export)
    geojson_resp = client.get(f"/api/files/{file_id}/features/")
    assert geojson_resp.status_code == 200
    geojson_data = geojson_resp.json()
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) == 3

def test_upload_shapefile_zip():
    zip_file = SAMPLE_DIR / "sample_shapes.zip"
    assert zip_file.exists()

    with open(zip_file, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_shapes.zip", f, "application/zip")}
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_shapes.zip"
    assert data["file_type"] == "SHAPEFILE_ZIP"
    assert data["feature_count"] == 3
    assert data["status"] == "COMPLETED"

    file_id = data["id"]

    # Verify measurements
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["polygon_count"] == 3
    assert meas_data["summary"]["total_area_sq_meters"] > 0
    assert meas_data["summary"]["total_area_hectares"] > 0

def test_invalid_file_extension():
    fake_txt = io.BytesIO(b"Hello world")
    response = client.post(
        "/api/files/",
        files={"file": ("notes.txt", fake_txt, "text/plain")}
    )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_corrupt_zip():
    bad_zip = io.BytesIO(b"Not a zip file content")
    response = client.post(
        "/api/files/",
        files={"file": ("broken.zip", bad_zip, "application/zip")}
    )
    assert response.status_code == 422
    assert "not a valid or readable ZIP" in response.json()["detail"]

def test_file_not_found():
    response = client.get("/api/files/nonexistent_id/")
    assert response.status_code == 404

def test_delete_file():
    kml_file = SAMPLE_DIR / "sample_survey.kml"
    with open(kml_file, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("temp_to_delete.kml", f, "application/vnd.google-earth.kml+xml")}
        )
    file_id = upload_resp.json()["id"]

    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 200

    # Ensure it no longer exists
    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 404
