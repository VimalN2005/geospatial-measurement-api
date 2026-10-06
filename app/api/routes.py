import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.models.schemas import (
    FileUploadResponse,
    FileInfoResponse,
    FileMeasurementsResponse,
    MeasurementSummary,
    FeatureMeasurement,
    GeoJSONFeatureCollection,
    GeoJSONFeature
)
from app.services.processor import processor
from app.services.shapefile_parser import ShapefileParsingError
from app.services.kml_parser import KMLParsingError
from app.models.storage import storage
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Geospatial Files"])

@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Process Geospatial File",
    description="Upload a .zip (Shapefile bundle) or .kml file. Extracts features, reprojects to appropriate UTM CRS, and computes measurements."
)
async def upload_geospatial_file(file: UploadFile = File(...)):
    filename = file.filename or "unknown"
    lower_name = filename.lower()

    if not (lower_name.endswith('.zip') or lower_name.endswith('.kml')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format for '{filename}'. Supported formats: Shapefile (.zip) or KML (.kml)."
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size ({settings.MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB)."
            )

        result = processor.process_file(filename=filename, content=content)
        return FileUploadResponse(
            id=result["id"],
            filename=result["filename"],
            file_type=result["file_type"],
            feature_count=result["feature_count"],
            crs=result["crs"],
            status=result["status"],
            message=f"Successfully extracted {result['feature_count']} features with CRS '{result['crs']}'."
        )

    except ShapefileParsingError as e:
        logger.error(f"Shapefile parsing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except KMLParsingError as e:
        logger.error(f"KML parsing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal processing error: {str(e)}"
        )


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get File Information",
    description="Returns metadata and processing status for an uploaded file by ID."
)
async def get_file_info(file_id: str):
    file_record = storage.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )

    return FileInfoResponse(
        id=file_record["id"],
        filename=file_record["filename"],
        feature_count=file_record["feature_count"],
        crs=file_record["crs"],
        status=file_record["status"]
    )


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get Feature Measurements",
    description="Returns calculated measurements (area in sq.m/ha/sq.km, length in m/km) for all features in the file."
)
async def get_file_measurements(file_id: str):
    file_record = storage.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )

    features = storage.get_features(file_id)
    summary_dict = file_record.get("summary", {})

    measurement_features = []
    for f in features:
        measurement_features.append(FeatureMeasurement(
            feature_index=f["feature_index"],
            feature_id=f.get("feature_id"),
            geometry_type=f["geometry_type"],
            measurement_type=f["measurement_type"],
            measurements=f.get("measurements"),
            properties=f.get("properties", {})
        ))

    return FileMeasurementsResponse(
        file_id=file_record["id"],
        filename=file_record["filename"],
        source_crs=file_record["crs"],
        projected_crs=file_record.get("projected_crs", "N/A"),
        projection_strategy=file_record.get("projection_strategy", "N/A"),
        summary=MeasurementSummary(**summary_dict),
        features=measurement_features
    )


@router.get(
    "/",
    response_model=List[FileInfoResponse],
    summary="List All Uploaded Files",
    description="Returns a list of all processed files."
)
async def list_files():
    files = storage.list_files()
    return [
        FileInfoResponse(
            id=f["id"],
            filename=f["filename"],
            feature_count=f["feature_count"],
            crs=f["crs"],
            status=f["status"]
        )
        for f in files
    ]


@router.get(
    "/{file_id}/features/",
    response_model=GeoJSONFeatureCollection,
    summary="Get GeoJSON FeatureCollection",
    description="Exports the file's features in standard GeoJSON format for mapping and GIS visualization."
)
async def get_geojson_features(file_id: str):
    file_record = storage.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )

    features = storage.get_features(file_id)
    geojson_features = []
    for f in features:
        if f.get("geometry"):
            geojson_features.append(GeoJSONFeature(
                id=f.get("feature_id"),
                geometry=f["geometry"],
                properties={**f.get("properties", {}), "measurements": f.get("measurements")}
            ))

    return GeoJSONFeatureCollection(
        file_id=file_record["id"],
        crs=file_record["crs"],
        features=geojson_features
    )


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_200_OK,
    summary="Delete File",
    description="Deletes a file record and its extracted features."
)
async def delete_file(file_id: str):
    deleted = storage.delete_file(file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )
    return {"message": f"File with ID '{file_id}' deleted successfully."}
