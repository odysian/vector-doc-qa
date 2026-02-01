from pathlib import Path

from app.constants import (
    ALLOWED_EXTENSIONS,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MAX_FILE_SIZE_BYTES,
)
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from env vars."""

    database_url: str = (
        "postgresql://postgres:postgres@localhost:5434/document_intelligence"
        "?options=-c%20search_path=quaero,public"
    )

    access_token_expire_minutes: int = 0
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    upload_dir: str = "uploads"
    max_file_size: int = MAX_FILE_SIZE_BYTES

    allowed_extensions: set[str] = ALLOWED_EXTENSIONS

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP

    whitelisted_ips: list[str] = []

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
