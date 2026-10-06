from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class FileUploadResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File format: SHAPEFILE_ZIP or KML")
    feature_count: int = Field(..., description="Total extracted features count")
    crs: str = Field(..., description="Source Coordinate Reference System")
    status: str = Field(..., description="Status: COMPLETED, FAILED, PROCESSING")
    message: Optional[str] = Field(None, description="Detailed processing status message")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FileInfoResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str
    status: str

class MeasurementDetail(BaseModel):
    area_sq_meters: Optional[float] = None
    area_hectares: Optional[float] = None
    area_sq_km: Optional[float] = None
    length_meters: Optional[float] = None
    length_km: Optional[float] = None
    note: Optional[str] = None

class FeatureMeasurement(BaseModel):
    feature_index: int
    feature_id: Optional[str] = None
    geometry_type: str
    measurement_type: str  # "area", "length", "none", "unsupported"
    measurements: Optional[MeasurementDetail] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    geometry_summary: Optional[Dict[str, Any]] = None

class MeasurementSummary(BaseModel):
    total_features: int
    polygon_count: int
    total_area_sq_meters: float
    total_area_hectares: float
    linestring_count: int
    total_length_meters: float
    point_count: int
    unsupported_count: int

class FileMeasurementsResponse(BaseModel):
    file_id: str
    filename: str
    source_crs: str
    projected_crs: str
    projection_strategy: str
    summary: MeasurementSummary
    features: List[FeatureMeasurement]

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: Optional[str] = None
    geometry: Dict[str, Any]
    properties: Dict[str, Any]

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    file_id: str
    crs: str
    features: List[GeoJSONFeature]
