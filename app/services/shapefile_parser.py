import io
import zipfile
import logging
from typing import Dict, Any, List, Tuple, Optional
import shapefile
from shapely.geometry import shape as to_shapely_shape
from shapely.geometry.base import BaseGeometry
from app.services.crs_service import crs_service

logger = logging.getLogger(__name__)

class ShapefileParsingError(Exception):
    pass

class ShapefileParser:
    """Parses zipped ESRI Shapefiles (.zip) into geometries, attributes, and CRS."""

    @classmethod
    def parse_zip_bytes(cls, zip_bytes: bytes) -> Tuple[List[Dict[str, Any]], str, Tuple[float, float, float, float]]:
        """Parses a zip archive containing Shapefile components.
        
        Returns:
            Tuple of:
                - List of feature dicts: [{ 'feature_index', 'feature_id', 'geometry', 'shapely_geom', 'properties' }]
                - Source CRS string (e.g. EPSG code or WKT name)
                - Bounding box (minx, miny, maxx, maxy)
        """
        try:
            zip_buffer = io.BytesIO(zip_bytes)
            with zipfile.ZipFile(zip_buffer, 'r') as z:
                names = z.namelist()
                # Find .shp file
                shp_files = [f for f in names if f.lower().endswith('.shp') and not f.startswith('__MACOSX')]
                if not shp_files:
                    raise ShapefileParsingError("The provided .zip archive does not contain a valid .shp file.")

                shp_filename = shp_files[0]
                base_name = shp_filename[:-4]

                # Check companion files
                shx_files = [f for f in names if f.lower() == (base_name + '.shx').lower()]
                dbf_files = [f for f in names if f.lower() == (base_name + '.dbf').lower()]

                if not shx_files or not dbf_files:
                    # Some zip files might have files in subfolders, try finding any .dbf/.shx
                    shx_files = [f for f in names if f.lower().endswith('.shx')]
                    dbf_files = [f for f in names if f.lower().endswith('.dbf')]
                    if not shx_files or not dbf_files:
                        raise ShapefileParsingError("Shapefile bundle is missing required .shx index or .dbf attributes file.")

                # Read .prj if available
                prj_files = [f for f in names if f.lower().endswith('.prj')]
                prj_wkt = None
                if prj_files:
                    try:
                        prj_wkt = z.read(prj_files[0]).decode('utf-8', errors='ignore')
                    except Exception as e:
                        logger.warning(f"Could not read .prj file: {e}")

                # Read files in-memory using pyshp
                shp_io = io.BytesIO(z.read(shp_filename))
                shx_io = io.BytesIO(z.read(shx_files[0]))
                dbf_io = io.BytesIO(z.read(dbf_files[0]))

                reader = shapefile.Reader(shp=shp_io, shx=shx_io, dbf=dbf_io)
                
                # Determine source CRS
                parsed_crs = crs_service.parse_source_crs(prj_content=prj_wkt)
                crs_identifier = parsed_crs.to_string()

                # Extract features
                features = []
                fields = [f[0] for f in reader.fields[1:]]  # exclude DeletionFlag

                all_minx, all_miny, all_maxx, all_maxy = float('inf'), float('inf'), float('-inf'), float('-inf')

                for idx, shape_record in enumerate(reader.shapeRecords()):
                    raw_shape = shape_record.shape
                    raw_record = shape_record.record

                    # Build properties dict
                    properties = {}
                    for field_name, value in zip(fields, raw_record):
                        if isinstance(value, bytes):
                            value = value.decode('utf-8', errors='ignore')
                        properties[field_name] = value

                    # Build geometry
                    try:
                        geo_dict = raw_shape.__geo_interface__
                        geom = to_shapely_shape(geo_dict)
                        if not geom.is_valid:
                            # Attempt healing invalid geometry
                            geom = geom.buffer(0)
                    except Exception as e:
                        logger.warning(f"Error converting shape index {idx} to Shapely: {e}")
                        geom = None

                    if geom and not geom.is_empty:
                        minx, miny, maxx, maxy = geom.bounds
                        all_minx = min(all_minx, minx)
                        all_miny = min(all_miny, miny)
                        all_maxx = max(all_maxx, maxx)
                        all_maxy = max(all_maxy, maxy)

                    features.append({
                        "feature_index": idx,
                        "feature_id": f"shp_{idx}",
                        "geometry_type": geom.geom_type if geom else "Unknown",
                        "geometry": raw_shape.__geo_interface__ if geom else None,
                        "shapely_geom": geom,
                        "properties": properties
                    })

                bounds = (all_minx, all_miny, all_maxx, all_maxy) if all_minx != float('inf') else (0.0, 0.0, 0.0, 0.0)
                return features, crs_identifier, bounds

        except zipfile.BadZipFile:
            raise ShapefileParsingError("Uploaded file is not a valid or readable ZIP archive.")
        except Exception as e:
            if isinstance(e, ShapefileParsingError):
                raise
            raise ShapefileParsingError(f"Shapefile processing error: {str(e)}")

shapefile_parser = ShapefileParser()
