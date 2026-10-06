# Geospatial File Measurement API

A production-grade backend service built with **FastAPI**, **Shapely**, and **PyProj** that accepts geospatial files (Zipped ESRI Shapefiles and OGC KML), extracts their geometric features, reprojects geographic coordinates to an appropriate local UTM projected coordinate system, and calculates accurate metric measurements (Polygon Area and LineString Length).

---

## Features

- **Multi-Format Ingestion**: Supports `.zip` (ESRI Shapefile bundle containing `.shp`, `.shx`, `.dbf`, and `.prj`) and `.kml` (OGC Keyhole Markup Language).
- **Intelligent CRS Reprojection**: Automatically detects geographic coordinate reference systems (e.g., `EPSG:4326`) and transforms geometries into the appropriate local **Universal Transverse Mercator (UTM)** projection for accurate Cartesian metric measurements (meters and square meters).
- **Precision Measurements**:
  - **Polygons & MultiPolygons**: Area in square meters ($m^2$), hectares ($ha$), and square kilometers ($km^2$), plus perimeter length.
  - **LineStrings & MultiLineStrings**: Planar length in linear meters ($m$) and kilometers ($km$).
  - **Points & MultiPoints**: Handled gracefully (zero-dimensional features have no area or length).
  - **Unsupported / Complex Geometries**: Handled gracefully without crashing.
- **RESTful Endpoints**: Clean API design adhering strictly to specification, including `/api/files/{id}/` metadata and `/api/files/{id}/measurements/`.
- **Interactive Documentation**: Auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`).
- **GeoJSON Export**: Auxiliary endpoint `/api/files/{id}/features/` for direct consumption by web mapping clients (Leaflet, Mapbox, QGIS).

---

## Table of Contents

- [Quick Start](#quick-start)
  - [Local Setup](#local-setup)
  - [Docker Setup](#docker-setup)
  - [Running Tests](#running-tests)
- [API Reference](#api-reference)
  - [1. Upload Geospatial File](#1-upload-geospatial-file)
  - [2. Get File Information](#2-get-file-information)
  - [3. Get Feature Measurements](#3-get-feature-measurements)
  - [4. Get GeoJSON FeatureCollection](#4-get-geojson-featurecollection)
  - [5. List Files](#5-list-files)
  - [6. Delete File](#6-delete-file)
- [Architecture & Processing Flow](#architecture--processing-flow)
  - [Directory Structure](#directory-structure)
  - [File Processing Flow](#file-processing-flow)
  - [CRS Handling Strategy](#crs-handling-strategy)
  - [Measurement Calculation Flow](#measurement-calculation-flow)
- [Design Decisions & Alternatives](#design-decisions--alternatives)
- [Learnings & Future Scope](#learnings--future-scope)

---

## Quick Start

### Local Setup

#### Prerequisites
- Python 3.10+
- `pip` and `virtualenv`

#### Steps

1. Clone the repository and navigate into the project directory:
   ```bash
   git clone <your-repo-url>
   cd geospatial-measurement-api
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Generate sample datasets (included in repository):
   ```bash
   python generate_samples.py
   ```

5. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. Open your browser:
   - Interactive Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - ReDoc Documentation: [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - Healthcheck: [http://localhost:8000/health](http://localhost:8000/health)

---

### Docker Setup

Run the application in an isolated container using Docker and Docker Compose:

```bash
docker compose up --build
```

The service will be accessible at `http://localhost:8000`.

---

### Running Tests

Execute the automated test suite using `pytest`:

```bash
pytest -v
```

All 8 tests cover end-to-end upload, KML parsing, Shapefile extraction, CRS transformation, measurement assertions, corrupt file rejection, and file deletion.

---

## API Reference

### 1. Upload Geospatial File
- **Endpoint**: `POST /api/files/`
- **Content-Type**: `multipart/form-data`
- **Supported Formats**: `.zip` (containing `.shp`, `.shx`, `.dbf`, `.prj`) or `.kml`

#### cURL Example (Uploading KML):
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@sample_data/sample_survey.kml"
```

#### cURL Example (Uploading Shapefile ZIP):
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@sample_data/sample_shapes.zip"
```

#### Sample Response (`201 Created`):
```json
{
  "id": "e4a2c18b",
  "filename": "sample_survey.kml",
  "file_type": "KML",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "message": "Successfully extracted 3 features with CRS 'EPSG:4326'.",
  "uploaded_at": "2026-10-06T18:45:00.000000Z"
}
```

---

### 2. Get File Information
- **Endpoint**: `GET /api/files/{id}/`
- **Description**: Returns metadata and processing status for an uploaded file.

#### cURL Example:
```bash
curl -X GET "http://localhost:8000/api/files/e4a2c18b/"
```

#### Sample Response (`200 OK`):
```json
{
  "id": "e4a2c18b",
  "filename": "sample_survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 3. Get Feature Measurements
- **Endpoint**: `GET /api/files/{id}/measurements/`
- **Description**: Returns projected measurements for all features in the file.

#### cURL Example:
```bash
curl -X GET "http://localhost:8000/api/files/e4a2c18b/measurements/"
```

#### Sample Response (`200 OK`):
```json
{
  "file_id": "e4a2c18b",
  "filename": "sample_survey.kml",
  "source_crs": "EPSG:4326",
  "projected_crs": "EPSG:32643",
  "projection_strategy": "Dynamic Local UTM Projection: Centroid (77.5890, 12.9693) projected to EPSG:32643 for true metric area and length calculations.",
  "summary": {
    "total_features": 3,
    "polygon_count": 1,
    "total_area_sq_meters": 191632.748,
    "total_area_hectares": 19.163275,
    "linestring_count": 1,
    "total_length_meters": 1548.914,
    "point_count": 1,
    "unsupported_count": 0
  },
  "features": [
    {
      "feature_index": 0,
      "feature_id": "Solar Array Plot A",
      "geometry_type": "Polygon",
      "measurement_type": "area",
      "measurements": {
        "area_sq_meters": 191632.748,
        "area_hectares": 19.163275,
        "area_sq_km": 0.191633,
        "length_meters": 1750.841,
        "length_km": 1.750841,
        "note": "Area calculated on projected Cartesian plane. Perimeter included as perimeter length."
      },
      "properties": {
        "name": "Solar Array Plot A",
        "description": "Perimeter boundary of primary solar panel deployment",
        "zone_type": "Industrial",
        "capacity_mw": "25.5"
      }
    },
    {
      "feature_index": 1,
      "feature_id": "HV Transmission Corridor",
      "geometry_type": "LineString",
      "measurement_type": "length",
      "measurements": {
        "area_sq_meters": 0.0,
        "length_meters": 1548.914,
        "length_km": 1.548914,
        "note": "Planar distance calculated in linear meters on projected coordinate system."
      },
      "properties": {
        "name": "HV Transmission Corridor",
        "voltage_kv": "66"
      }
    },
    {
      "feature_index": 2,
      "feature_id": "GCP Base Station 01",
      "geometry_type": "Point",
      "measurement_type": "none",
      "measurements": {
        "area_sq_meters": 0.0,
        "length_meters": 0.0,
        "note": "Point geometry: discrete zero-dimensional spatial coordinates have no area or length."
      },
      "properties": {
        "name": "GCP Base Station 01"
      }
    }
  ]
}
```

---

### 4. Get GeoJSON FeatureCollection
- **Endpoint**: `GET /api/files/{id}/features/`
- **Description**: Returns all features formatted as a standard GeoJSON FeatureCollection, suitable for rendering on interactive maps.

---

### 5. List Files
- **Endpoint**: `GET /api/files/`
- **Description**: Returns a list of all processed files.

---

### 6. Delete File
- **Endpoint**: `DELETE /api/files/{id}/`
- **Description**: Deletes a file record and its extracted features from storage.

---

## Architecture & Processing Flow

### Directory Structure

```
geospatial-measurement-api/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entrypoint & middleware
│   ├── config.py                # Environment configuration & settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic v2 request/response schemas
│   │   └── storage.py           # SQLite repository with thread-safe persistence
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crs_service.py       # CRS parsing, UTM zone determination & reprojection
│   │   ├── measurement.py       # Area & length calculations on planar geometries
│   │   ├── shapefile_parser.py  # In-memory shapefile zip extractor & parser (pyshp)
│   │   ├── kml_parser.py        # Secure XML KML parser (defusedxml)
│   │   └── processor.py         # Pipeline orchestrator
│   └── api/
│       ├── __init__.py
│       └── routes.py            # REST API route handlers
├── sample_data/
│   ├── sample_survey.kml        # Test KML dataset (Bengaluru survey)
│   └── sample_shapes.zip        # Test Shapefile dataset (.shp, .shx, .dbf, .prj)
├── tests/
│   ├── __init__.py
│   └── test_api.py              # Automated pytest suite (8 test cases)
├── Dockerfile                   # Production Docker container definition
├── docker-compose.yml           # Multi-container local orchestration
├── generate_samples.py          # Synthetic GIS test data generator
├── requirements.txt             # Locked Python dependencies
├── .gitignore
└── README.md
```

---

### File Processing Flow

```
[Client Upload: .zip / .kml]
             │
             ▼
[FastAPI /api/files/ Route]
             │
             ├── Validates extension (.zip or .kml) and payload size
             │
             ▼
[GeospatialProcessor.process_file]
             │
             ├── If .zip: ShapefileParser extracts .shp, .shx, .dbf, .prj in memory
             ├── If .kml: KMLParser parses XML Placemarks securely (defusedxml)
             │
             ▼
[Feature Extraction]
             ├── Extracts feature index, properties, geometry coordinates
             └── Computes dataset bounding box (minx, miny, maxx, maxy)
             │
             ▼
[CRS Detection & UTM Selection]
             ├── Reads source CRS (from .prj or KML default EPSG:4326)
             └── Computes dataset centroid -> Calculates optimal local UTM Zone
             │
             ▼
[Geometry Reprojection]
             └── PyProj Transformer (always_xy=True) reprojects to UTM meters
             │
             ▼
[Measurement Engine]
             ├── Polygon / MultiPolygon -> Planar Area (sq.m, ha, sq.km)
             ├── LineString / MultiLineString -> Planar Length (m, km)
             ├── Point / MultiPoint -> Measurement: None (Handled gracefully)
             └── Unsupported / Invalid -> Handled gracefully with warning note
             │
             ▼
[Persistence & Response]
             └── Saves to SQLite repository and returns 201 Created with metadata
```

---

### CRS Handling Strategy

A critical flaw in naive geospatial calculations is computing Euclidean area or distance directly on angular latitude/longitude coordinates (such as degrees in `EPSG:4326`). At non-equatorial latitudes, one degree of longitude does not equal one degree of latitude, causing severe spatial distortion.

#### Our Dynamic Projection Strategy:
1. **Source CRS Identification**:
   - For Shapefiles: Parsed from the ESRI WKT in the companion `.prj` file using `pyproj.CRS.from_wkt()`.
   - For KML: Standard OGC KML specification mandates coordinates in WGS 84 (`EPSG:4326`).
2. **Projected System Decision**:
   - If the source file is already in a projected planar system (e.g., State Plane or existing UTM), its native coordinate space is preserved.
   - If the source CRS is geographic (degrees), we calculate the spatial centroid $(\text{lon}_c, \text{lat}_c)$ of the dataset bounding box.
   - We calculate the appropriate **UTM Zone**:
     $$\text{Zone} = \left\lfloor \frac{\text{lon}_c + 180}{6} \right\rfloor + 1 \quad (\text{clamped } 1 \text{ to } 60)$$
   - We determine the hemisphere:
     $$\text{EPSG} = 32600 + \text{Zone} \quad (\text{if } \text{lat}_c \ge 0) \quad \text{or} \quad 32700 + \text{Zone} \quad (\text{if } \text{lat}_c < 0)$$
3. **Planar Transformation**:
   - A `pyproj.Transformer` is initialized with `always_xy=True` to guarantee that coordinates remain strictly mapped as $(x, y) \leftrightarrow (\text{longitude}, \text{latitude})$ regardless of PROJ version conventions.
   - Using `shapely.ops.transform`, geometries are reprojected into Cartesian meters prior to executing `.area` and `.length`.

---

### Measurement Calculation Flow

| Geometry Type | Target Metric | Metric Units Provided | Implementation |
| :--- | :--- | :--- | :--- |
| **Polygon / MultiPolygon** | Area & Perimeter | Square Meters ($m^2$), Hectares ($ha$), Square Kilometers ($km^2$), Meters ($m$) | `projected_geom.area`, `projected_geom.length` |
| **LineString / MultiLineString** | Length | Linear Meters ($m$), Kilometers ($km$) | `projected_geom.length` |
| **Point / MultiPoint** | None | Null / Handled gracefully with explicit note | Discrete points have 0 area & 0 length |
| **GeometryCollection** | Composite | Summed components | Component decomposition |
| **Unknown / Corrupted** | Graceful fallback | None (status `unsupported`) | Logs warning without crashing the service |

---

## Design Decisions & Alternatives

### 1. Framework: FastAPI vs Django REST Framework
- **Decision**: Selected **FastAPI**.
- **Rationale**:
  - Native asynchronous I/O and non-blocking request concurrency.
  - Automatic OpenAPI / Swagger generation (`/docs`) out of the box with zero boilerplate.
  - Strict data validation using Pydantic v2 with high execution speed.
  - Significantly lower container footprint and faster cold-start times compared to full Django.

### 2. GIS Parsing: PyShp + Shapely vs GDAL / Fiona
- **Decision**: Selected **PyShp (`pyshp`)** paired with **Shapely** and **PyProj**.
- **Rationale**:
  - Full GDAL and Fiona distributions require heavy, platform-specific C/C++ binaries that often fail or cause compiler friction during local installation on Windows and Linux.
  - `pyshp` is a pure-Python library that reads `.shp`, `.shx`, and `.dbf` streams directly from memory buffers (`io.BytesIO`) without writing temporary uncompressed files to disk.
  - `shapely` provides GEOS-backed geometry algorithms with pre-compiled wheels across all major operating systems.

### 3. XML Security in KML Parsing: `defusedxml`
- **Decision**: Used `defusedxml.ElementTree` instead of standard `xml.etree`.
- **Rationale**: Standard XML parsers are vulnerable to XML Entity Expansion (Billion Laughs attack) and external entity injection (XXE). `defusedxml` protects the production API against malicious XML payloads.

### 4. Storage Architecture: SQLite with Repository Pattern
- **Decision**: Implemented an encapsulated `StorageRepository` managing SQLite with connection pooling and thread safety.
- **Rationale**: Provides zero-configuration local persistence that works immediately without requiring an external PostgreSQL/PostGIS server, while allowing seamless replacement with PostgreSQL in production by modifying the repository adapter.

---

## Learnings & Future Scope

### Key Learnings
1. **Coordinate Axis Order Pitfalls**:
   Certain GIS standards order coordinates as $(latitude, longitude)$ while others use $(longitude, latitude)$ or $(x, y)$. Using `pyproj.Transformer.from_crs(..., always_xy=True)` prevents subtle axis-swapping bugs.
2. **XML Element Truthiness in Python 3.14**:
   In modern Python XML implementations, evaluating `if element:` tests child count rather than element existence. Testing `if element is not None:` is essential to avoid treating valid leaf nodes with text as falsy.
3. **Local UTM vs Global Equal Area**:
   While UTM minimizes conformal distortion locally within a 6-degree longitudinal band, global datasets spanning multiple continents require either multi-zone tiling or equal-area projections (like EPSG:6933 Equal Earth).

### Future Scope
1. **Asynchronous Task Queue (Celery + Redis)**:
   For drone photogrammetry files exceeding 500 MB (e.g. large survey orthomosaics or massive GeoTIFFs), offload processing to asynchronous background workers with webhook notifications.
2. **PostGIS Integration**:
   Transition from SQLite to PostgreSQL with PostGIS for spatial indexing (R-Tree GiST index), spatial queries, and topological intersections.
3. **3D Surface Area & Elevation Measurements**:
   Extend measurement engine to ingest 3D drone coordinates ($Z$ elevation values) to calculate true 3D surface area and volumetric cut-and-fill estimates across digital surface models (DSM).
4. **Cloud Object Storage (AWS S3 / Azure Blob)**:
   Stream uploaded archives directly to cloud buckets with signed URLs rather than local volume storage.

---

## Author

- **Vimal Sahani**  
  B.Tech Information Technology, IIIT Bhopal (Class of 2027)  
  Open Source Contributor (Celery, Django, Hugging Face)
