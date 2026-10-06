from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router as files_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Production-ready backend API service for ingesting geospatial data (Shapefile .zip and KML), "
        "reprojecting geographic coordinates (e.g. EPSG:4326) to appropriate local UTM projected coordinate systems, "
        "and computing precise metric measurements (Polygon Area, LineString Length)."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for GIS web clients & dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(files_router, prefix=settings.API_PREFIX)

@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "documentation": "/docs",
        "endpoints": {
            "upload": f"POST {settings.API_PREFIX}/files/",
            "file_info": f"GET {settings.API_PREFIX}/files/{{id}}/",
            "measurements": f"GET {settings.API_PREFIX}/files/{{id}}/measurements/",
            "geojson": f"GET {settings.API_PREFIX}/files/{{id}}/features/",
            "list_all": f"GET {settings.API_PREFIX}/files/"
        }
    }

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
