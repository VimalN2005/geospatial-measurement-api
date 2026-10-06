import logging
from typing import Optional, Dict, Any, Tuple
from shapely.geometry.base import BaseGeometry
from shapely.geometry import (
    Polygon, MultiPolygon, 
    LineString, MultiLineString, 
    Point, MultiPoint, 
    GeometryCollection
)
from app.models.schemas import MeasurementDetail

logger = logging.getLogger(__name__)

class MeasurementService:
    """Service to calculate geometric measurements on projected planar geometries."""

    @classmethod
    def calculate(cls, projected_geom: BaseGeometry) -> Tuple[str, Optional[MeasurementDetail]]:
        """Calculates measurement based on geometry type.
        
        Returns:
            Tuple[measurement_type, MeasurementDetail or None]
            measurement_type: 'area' | 'length' | 'none' | 'unsupported'
        """
        if projected_geom is None or projected_geom.is_empty:
            return "none", None

        geom_type = projected_geom.geom_type

        # 1. Polygon / MultiPolygon -> Calculate Area
        if isinstance(projected_geom, (Polygon, MultiPolygon)):
            area_sq_m = float(projected_geom.area)
            # Boundary length (perimeter) as supplementary metric
            perimeter_m = float(projected_geom.length)
            
            detail = MeasurementDetail(
                area_sq_meters=round(area_sq_m, 3),
                area_hectares=round(area_sq_m / 10_000.0, 6),
                area_sq_km=round(area_sq_m / 1_000_000.0, 6),
                length_meters=round(perimeter_m, 3),
                length_km=round(perimeter_m / 1000.0, 6),
                note="Area calculated on projected Cartesian plane. Perimeter included as perimeter length."
            )
            return "area", detail

        # 2. LineString / MultiLineString -> Calculate Length
        elif isinstance(projected_geom, (LineString, MultiLineString)):
            length_m = float(projected_geom.length)
            
            detail = MeasurementDetail(
                length_meters=round(length_m, 3),
                length_km=round(length_m / 1000.0, 6),
                area_sq_meters=0.0,
                note="Planar distance calculated in linear meters on projected coordinate system."
            )
            return "length", detail

        # 3. Point / MultiPoint -> No measurement required
        elif isinstance(projected_geom, (Point, MultiPoint)):
            detail = MeasurementDetail(
                area_sq_meters=0.0,
                length_meters=0.0,
                note="Point geometry: discrete zero-dimensional spatial coordinates have no area or length."
            )
            return "none", detail

        # 4. Graceful handling for other/unsupported types
        elif isinstance(projected_geom, GeometryCollection):
            # Sum areas and lengths of internal components gracefully
            total_area = float(projected_geom.area)
            total_len = float(projected_geom.length)
            detail = MeasurementDetail(
                area_sq_meters=round(total_area, 3),
                length_meters=round(total_len, 3),
                note="GeometryCollection composite measurement."
            )
            return "composite", detail

        else:
            logger.warning(f"Unsupported geometry type encountered: {geom_type}")
            detail = MeasurementDetail(
                note=f"Unsupported geometry type '{geom_type}' handled gracefully without calculation."
            )
            return "unsupported", detail

measurement_service = MeasurementService()
