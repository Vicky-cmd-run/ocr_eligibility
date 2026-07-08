"""
Application configuration using Pydantic Settings.
"""
from functools import lru_cache
from typing import Literal, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://ocr_user:ocr_password@localhost:5432/ocr_db"
    sync_database_url: str = "postgresql://ocr_user:ocr_password@localhost:5432/ocr_db"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # File Storage
    upload_dir: str = "/app/uploads"
    max_file_size_mb: int = 50
    allowed_extensions: str = "pdf,jpg,jpeg,png"

    # OCR
    ocr_confidence_auto_threshold: float = 0.90
    ocr_confidence_review_threshold: float = 0.75
    paddleocr_lang: str = "en"
    paddleocr_use_gpu: bool = False

    # Processing
    celery_concurrency: int = 4
    max_batch_size: int = 1000
    pdf_dpi: int = 200

    # Business Logic
    cutoff_formula: Literal["pcm_average", "engineering_200"] = "pcm_average"
    math_mode: Literal["combined", "simple_average"] = "combined"
    eligibility_threshold: float = 50.0

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
