import uuid

from app.config import settings
from app.core.security import decode_access_token
from app.utils.logging_config import get_logger
from fastapi import Request
from slowapi import Limiter

logger = get_logger(__name__)


def _is_ip_whitelisted(client_ip: str) -> bool:
    """Check if the given IP is in the whitelist."""
    whitelist = [ip.strip() for ip in settings.whitelisted_ips]
    return client_ip in whitelist


def _client_ip(request: Request) -> str:
    """Get client IP from request."""
    return request.client.host if request.client else "127.0.0.1"


def get_ip_key(request: Request) -> str:
    """
    Rate limit by IP. Used for unauthenticated endpoints (login, register).

    Logic:
    1. If the IP is in the whitelist, return a RANDOM UUID (bypass).
    2. Otherwise return the client IP.
    """
    client_ip = _client_ip(request)
    if _is_ip_whitelisted(client_ip):
        return str(uuid.uuid4())
    return client_ip


def get_user_or_ip_key(request: Request) -> str:
    """
    Rate limit by user ID when authenticated, else by IP.

    Whitelist is checked first: if the client IP is whitelisted, return a
    random UUID (bypass rate limit) regardless of auth. Otherwise:
    - Authenticated: rate limit by user_id
    - Unauthenticated: rate limit by IP
    """
    client_ip = _client_ip(request)
    if _is_ip_whitelisted(client_ip):
        return str(uuid.uuid4())

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = decode_access_token(token)
        if user_id:
            return f"user:{user_id}"
    return client_ip


limiter = Limiter(key_func=get_ip_key)

# Test rate limiter
# limiter = Limiter(key_func=lambda request: "test_user")
