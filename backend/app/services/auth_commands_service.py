from typing import NamedTuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.repositories.refresh_token_repository import (
    consume_refresh_token,
    create_refresh_token,
    delete_refresh_token,
)
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from app.schemas.user import UserCreate, UserLogin


class AuthTokenPair(NamedTuple):
    access_token: str
    refresh_token: str


async def register_user_command(
    *,
    db: AsyncSession,
    user: UserCreate,
) -> User:
    existing_user = await get_user_by_username(db=db, username=user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    existing_email = await get_user_by_email(db=db, email=user.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    return await create_user(
        db=db,
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
    )


async def login_user_command(
    *,
    db: AsyncSession,
    user: UserLogin,
) -> AuthTokenPair:
    db_user = await get_user_by_username(db=db, username=user.username)
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(data={"sub": str(db_user.id)})
    refresh_token = await create_refresh_token(db=db, user_id=db_user.id)
    await db.commit()

    return AuthTokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_auth_tokens_command(
    *,
    db: AsyncSession,
    refresh_token_value: str | None,
) -> AuthTokenPair:
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = await consume_refresh_token(db=db, token=refresh_token_value)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_refresh_token = await create_refresh_token(db=db, user_id=user_id)
    await db.commit()
    access_token = create_access_token(data={"sub": str(user_id)})

    return AuthTokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


async def logout_user_command(
    *,
    db: AsyncSession,
    refresh_token_value: str | None,
) -> None:
    await delete_refresh_token(db=db, token=refresh_token_value)
    await db.commit()
