import logging
import json
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.utils.logging_context import get_job_id, get_request_id

_LOG_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__.keys())
_RESERVED_EXTRA_KEYS = _LOG_RECORD_KEYS | {
    "service",
    "env",
    "version",
    "request_id",
    "job_id",
}


class _ContextFilter(logging.Filter):
    def __init__(self, *, service: str, env: str, version: str):
        super().__init__()
        self._service = service
        self._env = env
        self._version = version

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service
        record.env = self._env
        record.version = self._version
        record.request_id = getattr(record, "request_id", None) or get_request_id()
        record.job_id = getattr(record, "job_id", None) or get_job_id()
        return True


def _serialize_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _collect_extra_fields(record: logging.LogRecord) -> dict[str, object]:
    extras: dict[str, object] = {}
    for key, value in record.__dict__.items():
        if key in _RESERVED_EXTRA_KEYS or key.startswith("_"):
            continue
        if value is None:
            continue
        extras[key] = value
    return extras


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        service = getattr(record, "service", "unknown")
        env = getattr(record, "env", "unknown")
        version = getattr(record, "version", "unknown")
        request_id = getattr(record, "request_id", None)
        job_id = getattr(record, "job_id", None)
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": service,
            "env": env,
            "version": version,
        }
        if request_id is not None:
            payload["request_id"] = request_id
        if job_id is not None:
            payload["job_id"] = job_id
        payload.update(_collect_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class _KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        service = getattr(record, "service", "unknown")
        env = getattr(record, "env", "unknown")
        version = getattr(record, "version", "unknown")
        request_id = getattr(record, "request_id", None)
        job_id = getattr(record, "job_id", None)
        fields: dict[str, object] = {
            "service": service,
            "env": env,
            "version": version,
        }
        if request_id is not None:
            fields["request_id"] = request_id
        if job_id is not None:
            fields["job_id"] = job_id
        fields.update(_collect_extra_fields(record))
        rendered_fields = " ".join(
            f"{key}={_serialize_value(value)}" for key, value in fields.items()
        )
        return (
            f"{timestamp} {record.levelname} {record.name} {record.getMessage()} "
            f"{rendered_fields}"
        )


def _is_production_mode(app_env: str) -> bool:
    return app_env.strip().lower() in {"prod", "production"}


def setup_logging(
    log_level: str = "INFO",
    enable_file_logging: bool = True,
    log_file_max_bytes: int = 10 * 1024 * 1024,
    log_file_backup_count: int = 5,
    *,
    service: str,
    app_env: str,
    version: str,
) -> None:
    log_dir = Path("logs")
    if enable_file_logging:
        log_dir.mkdir(exist_ok=True)

    context_filter = _ContextFilter(
        service=service,
        env=app_env,
        version=version,
    )
    formatter: logging.Formatter
    if _is_production_mode(app_env):
        formatter = _JsonFormatter()
    else:
        formatter = _KeyValueFormatter()

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if enable_file_logging:
        handlers.append(
            RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=log_file_max_bytes,
                backupCount=log_file_backup_count,
            )
        )

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True,
    )

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("python_multipart").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    """
    return logging.getLogger(name)
