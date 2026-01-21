from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from env vars."""

    database_url: str = (
        "postgresql://postgres:postgres@localhost:5434/document_intelligence"
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB in bytes

    allowed_extensions: set[str] = {".pdf"}

    chunk_size: int = 500  # characters per chunk
    chunk_overlap: int = 50  # overlap between chunks

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
