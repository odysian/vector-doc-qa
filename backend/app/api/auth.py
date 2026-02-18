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
from app.utils.cookies import clear_auth_cookies, set_auth_cookies
from app.utils.rate_limit import get_ip_key, limiter
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
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
    response: Response,
    user: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with username and password.

    Returns a short-lived access token JWT and a long-lived refresh token
    in both the JSON body and as httpOnly cookies. Existing clients that
    read from the body continue to work unchanged.
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

    # Set httpOnly cookies; csrf_value is returned in the body for cross-domain
    # clients that cannot read a cookie set on a different origin (see ADR-001).
    csrf_value = set_auth_cookies(response, access_token, refresh_token)

    return {"access_token": access_token, "refresh_token": refresh_token, "csrf_token": csrf_value, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute", key_func=get_ip_key)
async def refresh(
    request: Request,
    response: Response,
    # Body is optional: cookie-based clients send no body; legacy clients send JSON
    body: RefreshRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access + refresh token pair (rotation).

    Token source priority: refresh_token cookie → request body.
    Old refresh token is deleted on use — if reused, it will 401.
    """
    # Cookie takes priority; body is the fallback for legacy clients
    refresh_token_value = request.cookies.get("refresh_token") or (
        body.refresh_token if body else None
    )
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    row = await validate_refresh_token(refresh_token_value, db)
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

    # Rotate cookies; return fresh csrf_token in body for cross-domain clients.
    csrf_value = set_auth_cookies(response, access_token, new_refresh_token)

    return {"access_token": access_token, "refresh_token": new_refresh_token, "csrf_token": csrf_value, "token_type": "bearer"}


@router.post("/logout")
@limiter.limit("10/minute", key_func=get_ip_key)
async def logout(
    request: Request,
    response: Response,
    # Body is optional: cookie-based clients send no body; legacy clients send JSON
    body: RefreshRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate a refresh token and clear auth cookies.

    Token source priority: refresh_token cookie → request body.
    Idempotent — no error if the token doesn't exist.
    """
    refresh_token_value = request.cookies.get("refresh_token") or (
        body.refresh_token if body else None
    )

    await db.execute(
        delete(RefreshToken).where(RefreshToken.token == refresh_token_value)
    )
    await db.commit()

    # Always clear cookies regardless of token source
    clear_auth_cookies(response)

    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.

    Accepts either an httpOnly access_token cookie or an Authorization: Bearer header.
    """
    return current_user
