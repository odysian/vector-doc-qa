from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_query_service import (
    get_authenticated_user_query,
    verify_csrf_query,
)

# auto_error=False: returns None instead of raising 401 when no Bearer header,
# so we can check for a cookie token first before deciding to 401.
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    return await get_authenticated_user_query(
        request=request,
        db=db,
        credentials=credentials,
    )


async def verify_csrf(request: Request) -> None:
    verify_csrf_query(request=request)


async def csrf_header_for_docs(
    x_csrf_token: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
        description=(
            "Required for cookie-authenticated mutating requests. "
            "Use csrf_token from login/refresh response or GET /api/auth/csrf."
        ),
    ),
) -> None:
    """
    OpenAPI-only helper: expose X-CSRF-Token header in Swagger UI.

    Runtime CSRF enforcement remains in verify_csrf().
    """
    del x_csrf_token
