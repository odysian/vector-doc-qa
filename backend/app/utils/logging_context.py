from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_job_id_ctx: ContextVar[str | None] = ContextVar("job_id", default=None)


def set_request_id(request_id: str | None) -> Token[str | None]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_job_id(job_id: str | None) -> Token[str | None]:
    return _job_id_ctx.set(job_id)


def reset_job_id(token: Token[str | None]) -> None:
    _job_id_ctx.reset(token)


def get_job_id() -> str | None:
    return _job_id_ctx.get()
