import asyncio
import shutil
from pathlib import Path
from typing import Protocol

from app.config import settings


class StorageBackend(Protocol):
    def write_bytes(
        self, relative_path: str, data: bytes, content_type: str | None = None
    ) -> None: ...
    def write_from_path(
        self, relative_path: str, source_path: str, content_type: str | None = None
    ) -> None: ...
    def read_bytes(self, relative_path: str) -> bytes: ...
    def delete(self, relative_path: str) -> None: ...


class LocalStorageBackend:
    """File-system storage backend used for local development/tests."""

    @staticmethod
    def _resolve(relative_path: str) -> Path:
        return settings.get_upload_path().parent / relative_path

    def write_bytes(
        self, relative_path: str, data: bytes, content_type: str | None = None
    ) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write_from_path(
        self, relative_path: str, source_path: str, content_type: str | None = None
    ) -> None:
        destination = self._resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)

    def read_bytes(self, relative_path: str) -> bytes:
        path = self._resolve(relative_path)
        return path.read_bytes()

    def delete(self, relative_path: str) -> None:
        path = self._resolve(relative_path)
        path.unlink(missing_ok=True)


class GCSStorageBackend:
    """Google Cloud Storage backend used in production."""

    def __init__(self) -> None:
        if not settings.gcs_bucket_name:
            raise RuntimeError("GCS_BUCKET_NAME must be set when STORAGE_BACKEND=gcs")

        try:
            from google.cloud import storage
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "google-cloud-storage is required when STORAGE_BACKEND=gcs"
            ) from exc

        self._not_found_exc: type[Exception] | None
        try:
            from google.api_core.exceptions import NotFound as GoogleNotFound

            self._not_found_exc = GoogleNotFound
        except Exception:
            self._not_found_exc = None

        self._client = storage.Client(project=settings.gcp_project_id or None)
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

    def write_bytes(
        self, relative_path: str, data: bytes, content_type: str | None = None
    ) -> None:
        blob = self._bucket.blob(relative_path)
        blob.upload_from_string(
            data, content_type=content_type or "application/octet-stream"
        )

    def write_from_path(
        self, relative_path: str, source_path: str, content_type: str | None = None
    ) -> None:
        blob = self._bucket.blob(relative_path)
        blob.upload_from_filename(
            source_path, content_type=content_type or "application/octet-stream"
        )

    def read_bytes(self, relative_path: str) -> bytes:
        blob = self._bucket.blob(relative_path)
        try:
            return blob.download_as_bytes()
        except Exception as exc:
            if self._not_found_exc and isinstance(exc, self._not_found_exc):
                raise FileNotFoundError(relative_path) from exc
            raise

    def delete(self, relative_path: str) -> None:
        blob = self._bucket.blob(relative_path)
        try:
            blob.delete()
        except Exception as exc:
            if self._not_found_exc and isinstance(exc, self._not_found_exc):
                return
            raise


_backend_instance: StorageBackend | None = None


def _build_backend() -> StorageBackend:
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorageBackend()
    if backend == "gcs":
        return GCSStorageBackend()
    raise RuntimeError(
        f"Unsupported STORAGE_BACKEND='{settings.storage_backend}'. Use 'local' or 'gcs'."
    )


def _get_backend() -> StorageBackend:
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = _build_backend()
    return _backend_instance


async def write_file_bytes(
    relative_path: str, data: bytes, content_type: str | None = None
) -> None:
    backend = _get_backend()
    await asyncio.to_thread(backend.write_bytes, relative_path, data, content_type)


async def write_file_from_path(
    relative_path: str, source_path: str, content_type: str | None = None
) -> None:
    backend = _get_backend()
    await asyncio.to_thread(
        backend.write_from_path, relative_path, source_path, content_type
    )


async def read_file_bytes(relative_path: str) -> bytes:
    backend = _get_backend()
    return await asyncio.to_thread(backend.read_bytes, relative_path)


async def delete_file(relative_path: str) -> None:
    backend = _get_backend()
    await asyncio.to_thread(backend.delete, relative_path)
