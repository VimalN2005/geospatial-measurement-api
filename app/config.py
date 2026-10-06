from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    UPLOAD_DIR: Path = Path("uploads")
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    DEFAULT_GEOGRAPHIC_CRS: str = "EPSG:4326"

    model_config = {
        "env_prefix": "GEOSPATIAL_",
        "case_sensitive": False
    }

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
