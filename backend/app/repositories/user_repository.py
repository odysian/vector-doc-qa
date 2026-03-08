from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_id(
    *,
    db: AsyncSession,
    user_id: int,
) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return await db.scalar(stmt)


async def get_user_by_username(
    *,
    db: AsyncSession,
    username: str,
) -> User | None:
    stmt = select(User).where(User.username == username)
    return await db.scalar(stmt)


async def get_user_by_email(
    *,
    db: AsyncSession,
    email: str,
) -> User | None:
    stmt = select(User).where(User.email == email)
    return await db.scalar(stmt)


async def create_user(
    *,
    db: AsyncSession,
    username: str,
    email: str,
    hashed_password: str,
) -> User:
    db_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
