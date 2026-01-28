from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.crud.user import get_user_by_id
from app.database import get_db
from app.models.user import User

# HTTP Bearer token security scheme
security = HTTPBearer()


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Extracts JWT from Authorization header, decodes it, and fetches user.
    Raises 401 if token is invalid or user not found.

    Usage in endpoints:
        @router.get("/me")
        def get_me(current_user: User = Depends(get_current_user)):
            return current_user
    """
    # Extract token from "Authorization: Bearer <token>" header
    token = credentials.credentials

    # Decode JWT to get user_id
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    user = get_user_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
