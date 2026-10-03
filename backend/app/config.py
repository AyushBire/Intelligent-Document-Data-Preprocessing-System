from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """Load validated runtime configuration from environment and dotenv files.

    Raises: ValidationError for missing required credentials or malformed values.
    """
    DATABASE_URL: SecretStr | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "idps"
    POSTGRES_DB: str = "idps"
    POSTGRES_PASSWORD: SecretStr | None = None
    AUTO_CREATE_TABLES: bool = False

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
        env_file=(Path(__file__).resolve().parents[2] / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        """Build the async database URL without interpolating passwords.

        Returns: PostgreSQL URL, or an explicitly configured async URL.
        Raises: ValueError for missing passwords or unsupported drivers.
        """
        if self.DATABASE_URL and self.DATABASE_URL.get_secret_value():
            url = make_url(self.DATABASE_URL.get_secret_value())
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+asyncpg")
            if url.drivername not in {"postgresql+asyncpg", "sqlite+aiosqlite"}:
                raise ValueError("Use PostgreSQL with asyncpg; SQLite is supported only for tests/imports.")
            return url
        if not self.POSTGRES_PASSWORD or not self.POSTGRES_PASSWORD.get_secret_value():
            raise ValueError("Set POSTGRES_PASSWORD or DATABASE_URL before starting IDPS.")
        return URL.create(
            "postgresql+asyncpg", username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(), host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT, database=self.POSTGRES_DB,
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse allowed origins. Returns: Nonempty origin strings. Raises: None."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings. Returns: Runtime configuration. Raises: ValidationError on invalid settings."""
    return Settings()
