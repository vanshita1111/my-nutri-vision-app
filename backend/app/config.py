"""
Application configuration via pydantic-settings.
All values can be overridden by environment variables or a .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal

# config.py lives at backend/app/config.py — walk up two levels to reach the
# nutrition-vision/ root where the shared .env file lives.
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(_ROOT_ENV), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_openssl_rand_hex_32"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://nutrition:nutrition@localhost:5432/nutrition_vision"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "nutrition-vision-images"
    S3_PREFIX: str = "uploads"

    # Models
    DEVICE: str = "cpu"  # "cuda" if GPU available
    YOLO_MODEL_PATH: str = "models/weights/food_detector_v1.onnx"
    SAM2_MODEL_PATH: str = "models/weights/sam2_hiera_large.pt"
    SAM2_CONFIG: str = "sam2_hiera_l.yaml"
    DEPTH_MODEL_ID: str = "depth-anything/Depth-Anything-V2-Small-hf"  # Small for CPU

    # Claude / Anthropic
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_TOKENS: int = 4096

    # Social auth
    GOOGLE_CLIENT_ID: str = ""          # Web OAuth client ID from Google Cloud Console
    APPLE_BUNDLE_ID: str = "com.nutrivision.app"  # Must match Apple app bundle ID

    # USDA
    USDA_API_KEY: str = ""
    USDA_API_BASE: str = "https://api.nal.usda.gov/fdc/v1"

    # Auth
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    ALLOWED_ORIGINS: list[str] = ['http://localhost:3000', 'http://localhost:8081', 'exp://localhost:8081', 'http://localhost:9000', 'https://leone-significance-bear-phones.trycloudflare.com']

    # Image limits
    MAX_IMAGE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    MIN_BLUR_SCORE: float = 50.0  # Laplacian variance threshold

    # Analysis
    YOLO_CONFIDENCE_THRESHOLD: float = 0.35
    YOLO_IOU_THRESHOLD: float = 0.45
    MAX_FOOD_ITEMS_PER_IMAGE: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
