import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken


async def create_refresh_token(
    *,
    db: AsyncSession,
    user_id: int,
) -> str:
    """
    Stage a new refresh token row. Does NOT commit — caller is responsible.
    """
    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    db.add(RefreshToken(user_id=user_id, token=raw_token, expires_at=expires_at))
    return raw_token


async def consume_refresh_token(
    *,
    db: AsyncSession,
    token: str,
) -> int | None:
    """
    Atomically consume an unexpired refresh token.

    Returns the token's user_id if the token existed and was valid; otherwise
    returns None. Does NOT commit — caller owns transaction boundaries.
    """
    stmt = (
        delete(RefreshToken)
        .where(
            RefreshToken.token == token,
            RefreshToken.expires_at >= func.now(),
        )
        .returning(RefreshToken.user_id)
    )
    return await db.scalar(stmt)


async def validate_refresh_token(
    *,
    db: AsyncSession,
    token: str,
) -> RefreshToken | None:
    """
    Look up a refresh token in the DB.

    Returns the RefreshToken row if found and not expired, otherwise None.
    Expired rows are staged for deletion. Caller owns commit/rollback.
    """
    stmt = select(RefreshToken).where(RefreshToken.token == token)
    row = await db.scalar(stmt)
    if row is None:
        return None
    expires_aware = (
        row.expires_at
        if row.expires_at.tzinfo is not None
        else row.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires_aware < datetime.now(timezone.utc):
        await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
        return None
    return row


async def delete_refresh_token(
    *,
    db: AsyncSession,
    token: str | None,
) -> None:
    if token is None:
        return
    await db.execute(delete(RefreshToken).where(RefreshToken.token == token))
