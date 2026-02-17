from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get user by ID."""
    stmt = select(User).where(User.id == user_id)
    return await db.scalar(stmt)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get user by username."""
    stmt = select(User).where(User.username == username)
    return await db.scalar(stmt)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email."""
    stmt = select(User).where(User.email == email)
    return await db.scalar(stmt)


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """
    Create a new user with hashed password.

    Args:
        db: Database session
        user: User creation data (includes plain password)

    Returns:
        Created user object
    """
    hashed_password = get_password_hash(user.password)

    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user
