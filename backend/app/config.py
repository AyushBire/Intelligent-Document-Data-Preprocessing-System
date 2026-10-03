from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — use postgresql+asyncpg://user:pass@host:5432/db in production
    DATABASE_URL: str = "sqlite+aiosqlite:///./idps.db"
    AUTO_CREATE_TABLES: bool = True  # dev only; set False in prod and use Alembic

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # File storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 20

    # Processing
    MAX_CONCURRENT_JOBS: int = 1   # EasyOCR is memory-heavy; keep low
    PRELOAD_MODELS: bool = True    # load OCR/LLM at startup instead of first request

    # CORS — comma-separated origins
    CORS_ORIGINS: str = "http://localhost:5173"

    # App
    APP_TITLE: str = "IDPS API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
