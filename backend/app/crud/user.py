from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Get user by ID."""
    stmt = select(User).where(User.id == user_id)
    return db.scalar(stmt)


def get_user_by_username(db: Session, username: str) -> User | None:
    """Get user by username."""
    stmt = select(User).where(User.username == username)
    return db.scalar(stmt)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email."""
    stmt = select(User).where(User.email == email)
    return db.scalar(stmt)


def create_user(db: Session, user: UserCreate) -> User:
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
    db.commit()
    db.refresh(db_user)

    return db_user
