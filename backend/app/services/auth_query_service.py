import secrets

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import get_user_by_id
from app.schemas.user import RefreshRequest

# Login/register are credential-gated and don't need CSRF protection.
_CSRF_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/register"}


async def get_authenticated_user_query(
    *,
    request: Request,
    db: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> User:
    cookie_token = request.cookies.get("access_token")
    bearer_token = credentials.credentials if credentials else None

    token = cookie_token or bearer_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_refresh_token_from_request_query(
    *,
    request: Request,
    body: RefreshRequest | None,
) -> str | None:
    return request.cookies.get("refresh_token") or (body.refresh_token if body else None)


def get_csrf_token_query(*, request: Request) -> str:
    csrf_token = request.cookies.get("csrf_token")
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSRF cookie not found. Login or refresh first.",
        )
    return csrf_token


def verify_csrf_query(*, request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    if request.url.path in _CSRF_EXEMPT_PATHS:
        return

    if not request.cookies.get("access_token"):
        return

    cookie_csrf = request.cookies.get("csrf_token")
    header_csrf = request.headers.get("X-CSRF-Token")

    if not cookie_csrf or not header_csrf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )

    if not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )
