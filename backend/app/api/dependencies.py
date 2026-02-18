import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.database import get_db
from app.models.user import User

# auto_error=False: returns None instead of raising 401 when no Bearer header,
# so we can check for a cookie token first before deciding to 401.
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """Extract the authenticated user from a cookie OR a Bearer token.

    Cookies are checked first (the production path after login).
    Bearer header is the fallback — keeps Swagger UI and existing API
    clients working without changes.
    """
    # Cookie path: httpOnly access_token set by login/refresh
    cookie_token = request.cookies.get("access_token")
    # Bearer path: Authorization: Bearer <token> header
    bearer_token = credentials.credentials if credentials else None

    token = cookie_token or bearer_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode JWT to get user_id
    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # A structurally valid JWT with a non-numeric sub should 401, not 500
    try:
        uid = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def verify_csrf(request: Request) -> None:
    """Enforce double-submit CSRF protection for cookie-authenticated requests.

    Rules:
    - Safe methods (GET, HEAD, OPTIONS) are always exempt.
    - If there is no access_token cookie the request is using Bearer auth,
      which is not vulnerable to CSRF (browser won't auto-send custom headers).
    - Otherwise: the X-CSRF-Token header must match the csrf_token cookie
      (timing-safe comparison).
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    # No access_token cookie → Bearer auth path → no CSRF risk
    if not request.cookies.get("access_token"):
        return

    cookie_csrf = request.cookies.get("csrf_token")
    header_csrf = request.headers.get("X-CSRF-Token")

    if not cookie_csrf or not header_csrf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )

    # Timing-safe comparison prevents timing-oracle attacks
    if not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )
