import uuid
import logging
from typing import Dict, Any, Tuple
from pyproj import CRS
from app.services.shapefile_parser import shapefile_parser, ShapefileParsingError
from app.services.kml_parser import kml_parser, KMLParsingError
from app.services.crs_service import crs_service
from app.services.measurement import measurement_service
from app.models.storage import storage

logger = logging.getLogger(__name__)

class GeospatialProcessor:
    """Orchestrates parsing, CRS transformation, measurement calculation, and persistence."""

    @classmethod
    def process_file(cls, filename: str, content: bytes) -> Dict[str, Any]:
        """Processes an uploaded file (.zip containing Shapefile or .kml)."""
        lower_name = filename.lower()
        file_id = uuid.uuid4().hex[:8]

        # 1. Format Detection & Parsing
        if lower_name.endswith('.zip'):
            file_type = "SHAPEFILE_ZIP"
            raw_features, source_crs_str, bounds = shapefile_parser.parse_zip_bytes(content)
        elif lower_name.endswith('.kml'):
            file_type = "KML"
            raw_features, source_crs_str, bounds = kml_parser.parse_kml_bytes(content)
        else:
            raise ValueError(f"Unsupported file format '{filename}'. Allowed formats: .zip (Shapefile) or .kml.")

        # 2. CRS Resolution & Projected CRS Selection
        source_crs = crs_service.parse_source_crs(crs_name=source_crs_str)
        projected_crs, projection_strategy = crs_service.select_projected_crs(source_crs, bounds)
        
        # 3. Coordinate Transformer Initialization
        transformer = crs_service.create_transformer(source_crs, projected_crs)

        # 4. Measurement Calculation
        processed_features = []
        total_area_sq_m = 0.0
        total_length_m = 0.0
        polygon_count = 0
        linestring_count = 0
        point_count = 0
        unsupported_count = 0

        for f in raw_features:
            shapely_geom = f.get("shapely_geom")
            measurement_detail = None
            measurement_type = "none"

            if shapely_geom and not shapely_geom.is_empty:
                # Transform to projected planar coordinate system (meters)
                projected_geom = crs_service.transform_geometry(shapely_geom, transformer)
                m_type, m_detail = measurement_service.calculate(projected_geom)
                measurement_type = m_type
                measurement_detail = m_detail

                if m_type == "area" and m_detail and m_detail.area_sq_meters:
                    total_area_sq_m += m_detail.area_sq_meters
                    polygon_count += 1
                elif m_type == "length" and m_detail and m_detail.length_meters:
                    total_length_m += m_detail.length_meters
                    linestring_count += 1
                elif m_type == "none":
                    point_count += 1
                else:
                    unsupported_count += 1
            else:
                measurement_type = "unsupported"
                unsupported_count += 1

            processed_features.append({
                "feature_index": f["feature_index"],
                "feature_id": f.get("feature_id"),
                "geometry_type": f["geometry_type"],
                "geometry": f.get("geometry"),
                "properties": f.get("properties", {}),
                "measurement_type": measurement_type,
                "measurements": measurement_detail.model_dump() if measurement_detail else None
            })

        summary = {
            "total_features": len(processed_features),
            "polygon_count": polygon_count,
            "total_area_sq_meters": round(total_area_sq_m, 3),
            "total_area_hectares": round(total_area_sq_m / 10_000.0, 6),
            "linestring_count": linestring_count,
            "total_length_meters": round(total_length_m, 3),
            "point_count": point_count,
            "unsupported_count": unsupported_count
        }

        # 5. Persist File Metadata & Features
        file_record = {
            "id": file_id,
            "filename": filename,
            "file_type": file_type,
            "feature_count": len(processed_features),
            "crs": source_crs.to_string(),
            "status": "COMPLETED",
            "projected_crs": projected_crs.to_string(),
            "projection_strategy": projection_strategy,
            "summary": summary
        }

        storage.save_file_record(file_record)
        storage.save_features(file_id, processed_features)

        logger.info(f"Processed file '{filename}' with ID '{file_id}'. {len(processed_features)} features.")
        return file_record

processor = GeospatialProcessor()
