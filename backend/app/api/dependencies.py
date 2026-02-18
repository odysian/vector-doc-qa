from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.database import get_db
from app.models.user import User

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Extracts JWT from Authorization header, decodes it, and fetches user.
    Raises 401 if token is invalid or user not found.

    Usage in endpoints:
        @router.get("/me")
        async def get_me(current_user: User = Depends(get_current_user)):
            return current_user
    """
    # Extract token from "Authorization: Bearer <token>" header
    token = credentials.credentials

    # Decode JWT to get user_id
    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convert to int — a structurally valid JWT with a non-numeric sub
    # should return 401, not an unhandled 500 from ValueError.
    try:
        uid = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    user = await get_user_by_id(db, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
