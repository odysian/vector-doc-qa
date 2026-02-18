import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash plain password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dict to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[str]:
    """
    Decode a JWT token and extract the subject (user ID).

    Args:
        token: JWT token string

    Returns:
        User ID from token, or None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")  # type: ignore
        return user_id
    except JWTError:
        return None


async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    """
    Stage a new refresh token row. Does NOT commit — caller is responsible.

    This keeps the caller in control of transaction boundaries, which matters
    for the refresh endpoint where the delete and insert must be atomic.
    """
    # Import here to avoid circular imports (models → base → security)
    from app.models.refresh_token import RefreshToken

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    db.add(RefreshToken(user_id=user_id, token=raw_token, expires_at=expires_at))
    return raw_token


async def validate_refresh_token(
    token: str, db: AsyncSession
) -> Optional["RefreshToken"]:
    """
    Look up a refresh token in the DB.

    Returns the RefreshToken row if found and not expired, otherwise None.
    Does NOT delete the row — callers handle deletion for rotation/expiry.
    """
    from app.models.refresh_token import RefreshToken

    stmt = select(RefreshToken).where(RefreshToken.token == token)
    row = await db.scalar(stmt)
    if row is None:
        return None
    # Make expires_at timezone-aware if the driver returned a naive datetime.
    # DateTime(timezone=True) with asyncpg should always return aware, but
    # .replace() on an already-aware value is wrong if tzinfo != UTC.
    expires_aware = (
        row.expires_at
        if row.expires_at.tzinfo is not None
        else row.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires_aware < datetime.now(timezone.utc):
        # Expired — clean up and signal failure
        await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
        await db.commit()
        return None
    return row
