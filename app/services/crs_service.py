import math
import logging
from typing import Tuple, Optional
import pyproj
from pyproj import CRS, Transformer
import shapely
from shapely.ops import transform
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)

class CRSService:
    """Service to handle Coordinate Reference System parsing, UTM projection selection, and transformation."""

    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    def parse_source_crs(cls, prj_content: Optional[str] = None, crs_name: Optional[str] = None) -> CRS:
        """Parses source CRS from ESRI WKT (.prj file) or string identifier, defaulting to EPSG:4326."""
        if prj_content and prj_content.strip():
            try:
                # Try parsing WKT
                return CRS.from_wkt(prj_content.strip())
            except Exception as e:
                logger.warning(f"Failed to parse CRS from WKT string: {e}. Trying user input fallback.")
                try:
                    return CRS.from_user_input(prj_content.strip())
                except Exception:
                    pass

        if crs_name and crs_name.strip():
            try:
                return CRS.from_user_input(crs_name.strip())
            except Exception as e:
                logger.warning(f"Failed to parse CRS name '{crs_name}': {e}.")

        # Default to standard WGS 84
        logger.info(f"Defaulting to standard geographic CRS: {cls.DEFAULT_GEOGRAPHIC_CRS}")
        return CRS.from_user_input(cls.DEFAULT_GEOGRAPHIC_CRS)

    @classmethod
    def get_utm_epsg_for_coordinates(cls, lon: float, lat: float) -> int:
        """Determines the appropriate UTM EPSG code for a given longitude and latitude.
        
        Formula:
            Zone = floor((lon + 180) / 6) + 1 (clamped 1-60)
            Northern Hemisphere (lat >= 0): EPSG = 32600 + zone
            Southern Hemisphere (lat < 0): EPSG = 32700 + zone
        """
        # Normalize longitude between -180 and 180
        norm_lon = ((lon + 180.0) % 360.0) - 180.0
        zone = int((norm_lon + 180.0) / 6.0) + 1
        zone = max(1, min(60, zone))

        if lat >= 0:
            epsg = 32600 + zone
        else:
            epsg = 32700 + zone
        return epsg

    @classmethod
    def select_projected_crs(cls, source_crs: CRS, bounds: Tuple[float, float, float, float]) -> Tuple[CRS, str]:
        """Selects an appropriate projected coordinate system for metric measurements.
        
        Args:
            source_crs: The parsed source CRS.
            bounds: (minx, miny, maxx, maxy) bounding box of the dataset.

        Returns:
            Tuple[CRS, str]: (selected projected CRS, strategy explanation)
        """
        if source_crs.is_projected:
            # If the source file is already projected (e.g. already in UTM or local state plane),
            # we can verify it operates in linear meters.
            axis_info = source_crs.axis_info
            units = axis_info[0].unit_name if axis_info else "unknown"
            strategy = f"Source CRS is already projected ({source_crs.to_string()}, linear units: {units})."
            return source_crs, strategy

        # If source CRS is geographic (degrees, e.g., EPSG:4326):
        minx, miny, maxx, maxy = bounds
        centroid_lon = (minx + maxx) / 2.0
        centroid_lat = (miny + maxy) / 2.0

        utm_epsg = cls.get_utm_epsg_for_coordinates(centroid_lon, centroid_lat)
        target_crs = CRS.from_epsg(utm_epsg)
        strategy = (
            f"Dynamic Local UTM Projection: Centroid ({centroid_lon:.4f}, {centroid_lat:.4f}) "
            f"projected to EPSG:{utm_epsg} for true metric area and length calculations."
        )
        return target_crs, strategy

    @classmethod
    def create_transformer(cls, source_crs: CRS, target_crs: CRS) -> Transformer:
        """Creates a pyproj Transformer ensuring always_xy=True to avoid coordinate inversion."""
        return Transformer.from_crs(source_crs, target_crs, always_xy=True)

    @classmethod
    def transform_geometry(cls, geom: BaseGeometry, transformer: Transformer) -> BaseGeometry:
        """Projects a shapely geometry to target coordinate space using transformer."""
        if geom is None or geom.is_empty:
            return geom
        return transform(transformer.transform, geom)

crs_service = CRSService()
