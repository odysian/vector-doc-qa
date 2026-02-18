from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    validate_refresh_token,
    verify_password,
)
from app.crud.user import create_user, get_user_by_email, get_user_by_username
from app.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import RefreshRequest, Token, UserCreate, UserLogin, UserResponse
from app.utils.rate_limit import get_ip_key, limiter
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/hour", key_func=get_ip_key)
async def register(
    request: Request,
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.

    - Checks if username or email already exists
    - Hashes password before storing
    - Returns created user (without password)
    """
    # Check if username already exists
    db_user = await get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    db_user = await get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user (password hashing happens in CRUD)
    return await create_user(db, user)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute", key_func=get_ip_key)
async def login(
    request: Request,
    user: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with username and password.

    Returns a short-lived access token JWT and a long-lived refresh token.
    """
    db_user = await get_user_by_username(db, user.username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(user.password, db_user.hashed_password):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(data={"sub": str(db_user.id)})
    refresh_token = await create_refresh_token(db_user.id, db)  # type: ignore
    await db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute", key_func=get_ip_key)
async def refresh(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access + refresh token pair (rotation).

    Old refresh token is deleted on use — if reused, it will 401.
    """
    row = await validate_refresh_token(body.refresh_token, db)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id: int = row.user_id  # type: ignore

    # Rotation: delete consumed token and stage new one in the same transaction
    await db.execute(delete(RefreshToken).where(RefreshToken.id == row.id))
    new_refresh_token = await create_refresh_token(user_id, db)
    await db.commit()  # single commit — both operations succeed or both roll back

    access_token = create_access_token(data={"sub": str(user_id)})

    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}


@router.post("/logout")
@limiter.limit("10/minute", key_func=get_ip_key)
async def logout(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate a refresh token. Idempotent — no error if the token doesn't exist.
    """
    await db.execute(
        delete(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    await db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.

    Requires authentication (JWT token in Authorization header).
    """
    return current_user
