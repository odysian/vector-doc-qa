import uuid

from app.config import settings
from app.core.security import decode_access_token
from app.utils.logging_config import get_logger
from fastapi import Request
from slowapi import Limiter

logger = get_logger(__name__)


def get_ip_key(request: Request) -> str:
    """
    Rate limit by IP. Used for unauthenticated endpoints (login, register).

    Logic:
    1. If the IP is in the whitelist, return a RANDOM UUID.
    2. Otherwise return the client IP.
    """
    if not request.client:
        return "127.0.0.1"

    client_ip = request.client.host
    whitelist = [ip.strip() for ip in settings.whitelisted_ips]
    if client_ip in whitelist:
        return str(uuid.uuid4())
    return client_ip


def get_user_or_ip_key(request: Request) -> str:
    """
    Rate limit by user ID when authenticated, else by IP.

    For auth-required endpoints: uses JWT to get user_id, so each user
    has their own limit regardless of IP. Prevents one account from
    bypassing limits via IP rotation.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = decode_access_token(token)
        if user_id:
            return f"user:{user_id}"
    return get_ip_key(request)


limiter = Limiter(key_func=get_ip_key)

# Test rate limiter
# limiter = Limiter(key_func=lambda request: "test_user")
