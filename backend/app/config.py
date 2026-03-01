from pathlib import Path
from urllib.parse import unquote, urlparse

from app.constants import (
    ALLOWED_EXTENSIONS,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MAX_FILE_SIZE_BYTES,
)
from pydantic import model_validator
from pydantic_settings import BaseSettings


NON_STRICT_APP_ENVS = {"local", "development", "dev", "test"}
FORBIDDEN_SECRET_KEY_VALUES = {
    "dev-secret-key-change-in-production",
    "changeme",
    "change-me",
    "replace-me",
    "your-secret-key",
}
FORBIDDEN_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}
FORBIDDEN_DB_NAMES = {"document_intelligence"}
FORBIDDEN_DB_CREDENTIALS = {
    ("postgres", "postgres"),
    ("postgres", "password"),
}


class Settings(BaseSettings):
    """Application settings loaded from env vars."""

    app_env: str = "development"

    database_url: str = (
        "postgresql://postgres:postgres@localhost:5434/document_intelligence"
        "?options=-c%20search_path=quaero,public"
    )

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    upload_dir: str = "uploads"
    max_file_size: int = MAX_FILE_SIZE_BYTES
    storage_backend: str = "local"
    gcs_bucket_name: str = ""
    gcp_project_id: str = ""

    allowed_extensions: set[str] = ALLOWED_EXTENSIONS

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP

    frontend_url: str = "http://localhost:3000"
    port: int = 8000

    whitelisted_ips: list[str] = []
    trusted_proxy_ips: list[str] = []

    redis_url: str = "redis://localhost:6379/0"
    arq_queue_name: str = "quaero:queue"
    arq_poll_delay_seconds: float = 10.0
    arq_job_timeout_seconds: int = 900
    arq_max_jobs: int = 1
    arq_stale_processing_minutes: int = 15

    log_level: str = "INFO"
    enable_file_logging: bool = True
    log_file_max_bytes: int = 10 * 1024 * 1024
    log_file_backup_count: int = 5

    @property
    def is_strict_environment(self) -> bool:
        """Return True when startup guardrails should fail closed."""
        return self.app_env.strip().lower() not in NON_STRICT_APP_ENVS

    @property
    def async_database_url(self) -> str:
        """Convert sync database URL to asyncpg format.

        Replaces the driver prefix and strips the ?options= query parameter
        because asyncpg uses connect_args for server settings instead.
        """
        url = self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        # Strip ?options= param — asyncpg handles search_path via connect_args
        if "?options=" in url:
            url = url[: url.index("?options=")]
        return url

    @model_validator(mode="after")
    def validate_runtime_security_guardrails(self) -> "Settings":
        """Fail startup in strict environments when security config is unsafe."""
        if not self.is_strict_environment:
            return self

        errors: list[str] = []
        secret_key = self.secret_key.strip()
        normalized_secret_key = secret_key.lower()

        if len(secret_key) < 32:
            errors.append(
                "SECRET_KEY must be at least 32 characters in strict environments"
            )
        if normalized_secret_key in FORBIDDEN_SECRET_KEY_VALUES:
            errors.append(
                "SECRET_KEY uses a forbidden dev/default value in strict environments"
            )
        if "<" in secret_key and ">" in secret_key:
            errors.append(
                "SECRET_KEY contains placeholder syntax; set a real secret value"
            )

        parsed_db_url = urlparse(self.database_url)
        if not parsed_db_url.scheme.startswith("postgresql"):
            errors.append("DATABASE_URL must use a PostgreSQL URL in strict environments")

        db_host = (parsed_db_url.hostname or "").strip().lower()
        if db_host in FORBIDDEN_DB_HOSTS:
            errors.append("DATABASE_URL must not use localhost/loopback in strict mode")

        db_name = parsed_db_url.path.lstrip("/").lower()
        if db_name in FORBIDDEN_DB_NAMES:
            errors.append(
                "DATABASE_URL must not use the default dev database name in strict mode"
            )

        db_username = unquote(parsed_db_url.username or "").strip().lower()
        db_password = unquote(parsed_db_url.password or "").strip().lower()
        if (db_username, db_password) in FORBIDDEN_DB_CREDENTIALS:
            errors.append(
                "DATABASE_URL must not use default dev credentials in strict mode"
            )

        if "<" in self.database_url and ">" in self.database_url:
            errors.append(
                "DATABASE_URL contains placeholder syntax; set real connection values"
            )

        if errors:
            error_list = "; ".join(errors)
            raise ValueError(f"Unsafe runtime configuration: {error_list}")

        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_upload_path(self) -> Path:
        """
        Get the absolute path to the uploads directory.
        Creates the directory if it doesn't exist.
        """
        upload_path = Path(__file__).parent.parent / self.upload_dir
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path


settings = Settings()
