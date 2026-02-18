"""Cookie helpers for httpOnly auth token transport.

Sets/clears the three auth cookies:
  - access_token  (httpOnly, Path=/api/)
  - refresh_token (httpOnly, Path=/api/auth/)
  - csrf_token    (NOT httpOnly — JS reads it for double-submit CSRF protection)
"""

import secrets
from typing import Literal

from fastapi import Response

from app.config import settings


def _is_production() -> bool:
    """Return True when the frontend URL is HTTPS (i.e. production)."""
    return settings.frontend_url.startswith("https://")


def set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """Set all three auth cookies on the response.

    SameSite=None requires Secure=True (enforced automatically in prod).
    In dev (http), SameSite=Lax is used so cookies work without HTTPS.
    """
    prod = _is_production()
    secure = prod
    # SameSite=None requires Secure; Lax works in dev without HTTPS
    samesite: Literal["lax", "strict", "none"] = "none" if prod else "lax"

    # access_token_expire_minutes == 0 → no expiry configured → session cookie
    access_max_age: int | None = settings.access_token_expire_minutes * 60 or None
    refresh_max_age: int = settings.refresh_token_expire_days * 86400

    # httpOnly: cannot be read by JS — protects against XSS token theft
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/api/",
        max_age=access_max_age,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/api/auth/",
        max_age=refresh_max_age,
    )

    # csrf_token is NOT httpOnly — the frontend reads it via document.cookie
    # and echoes it back as the X-CSRF-Token request header.
    csrf_value = secrets.token_hex(16)
    response.set_cookie(
        key="csrf_token",
        value=csrf_value,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=access_max_age,
    )


def clear_auth_cookies(response: Response) -> None:
    """Delete all three auth cookies by overwriting them with max_age=0.

    The path must match the path used when setting the cookie, otherwise
    the browser treats them as different cookies and keeps the originals.
    """
    prod = _is_production()
    secure = prod
    samesite: Literal["lax", "strict", "none"] = "none" if prod else "lax"

    cookie_attrs: list[tuple[str, str, bool]] = [
        ("access_token", "/api/", True),
        ("refresh_token", "/api/auth/", True),
        ("csrf_token", "/", False),
    ]
    for key, path, httponly in cookie_attrs:
        response.set_cookie(
            key=key,
            value="",
            max_age=0,
            httponly=httponly,
            secure=secure,
            samesite=samesite,
            path=path,
        )
