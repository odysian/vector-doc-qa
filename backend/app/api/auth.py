from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    CsrfTokenResponse,
    RefreshRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_commands_service import (
    login_user_command,
    logout_user_command,
    refresh_auth_tokens_command,
    register_user_command,
)
from app.services.auth_query_service import (
    get_csrf_token_query,
    get_refresh_token_from_request_query,
)
from app.utils.cookies import clear_auth_cookies, set_auth_cookies
from app.utils.rate_limit import get_ip_key, limiter
from fastapi import APIRouter, Body, Depends, Request, Response, status
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
    del request
    return await register_user_command(db=db, user=user)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute", key_func=get_ip_key)
async def login(
    request: Request,
    response: Response,
    user: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    del request
    tokens = await login_user_command(db=db, user=user)
    csrf_value = set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    return {"csrf_token": csrf_value, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute", key_func=get_ip_key)
async def refresh(
    request: Request,
    response: Response,
    # Body is optional: cookie-based clients send no body; legacy clients send JSON
    body: RefreshRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    refresh_token_value = get_refresh_token_from_request_query(
        request=request,
        body=body,
    )
    tokens = await refresh_auth_tokens_command(
        db=db,
        refresh_token_value=refresh_token_value,
    )
    csrf_value = set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    return {"csrf_token": csrf_value, "token_type": "bearer"}


@router.post("/logout")
@limiter.limit("10/minute", key_func=get_ip_key)
async def logout(
    request: Request,
    response: Response,
    # Body is optional: cookie-based clients send no body; legacy clients send JSON
    body: RefreshRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    refresh_token_value = get_refresh_token_from_request_query(
        request=request,
        body=body,
    )
    await logout_user_command(db=db, refresh_token_value=refresh_token_value)
    clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.

    Accepts either an httpOnly access_token cookie or an Authorization: Bearer header.
    """
    return current_user


@router.get("/csrf", response_model=CsrfTokenResponse)
async def get_csrf_token(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    del current_user
    return {"csrf_token": get_csrf_token_query(request=request)}
