import ipaddress
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


def _parse_ip(ip: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return a parsed IP address, or None for invalid values."""
    try:
        return ipaddress.ip_address(ip.strip())
    except ValueError:
        return None


def _is_trusted_proxy(client_ip: str) -> bool:
    """Check whether the direct peer IP belongs to a trusted proxy range."""
    client_ip_obj = _parse_ip(client_ip)
    if client_ip_obj is None:
        return False

    for proxy_ip in settings.trusted_proxy_ips:
        candidate = proxy_ip.strip()
        if not candidate:
            continue
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy entry: %s", proxy_ip)
            continue
        if client_ip_obj in network:
            return True
    return False


def _resolve_forwarded_for_client_ip(
    x_forwarded_for: str, peer_ip: str
) -> str | None:
    """
    Resolve the client IP from a trusted X-Forwarded-For chain.

    The chain is interpreted right-to-left and trusted hops are stripped until
    the first untrusted IP is found. This avoids trusting client-injected
    left-most values.
    """
    forwarded_ips = [entry.strip() for entry in x_forwarded_for.split(",") if entry.strip()]
    if not forwarded_ips:
        return None

    normalized_chain: list[str] = []
    for ip in forwarded_ips:
        parsed_ip = _parse_ip(ip)
        if parsed_ip is None:
            return None
        normalized_chain.append(str(parsed_ip))

    normalized_chain.append(peer_ip)

    for hop_ip in reversed(normalized_chain):
        if _is_trusted_proxy(hop_ip):
            continue
        return hop_ip

    return None


def _client_ip(request: Request) -> str:
    """
    Derive client IP safely.

    Forwarded headers are only trusted when the direct peer is configured as a
    trusted proxy. Otherwise, spoofed headers are ignored.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if not _is_trusted_proxy(peer_ip):
        return peer_ip

    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        forwarded_client_ip = _resolve_forwarded_for_client_ip(x_forwarded_for, peer_ip)
        if forwarded_client_ip:
            return forwarded_client_ip

    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        parsed_ip = _parse_ip(x_real_ip)
        if parsed_ip:
            return str(parsed_ip)

    return peer_ip


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

    # Cookie fallback: rate limit by user when authenticated via httpOnly cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        user_id = decode_access_token(cookie_token)
        if user_id:
            return f"user:{user_id}"

    return client_ip


limiter = Limiter(key_func=get_ip_key)

# Test rate limiter
# limiter = Limiter(key_func=lambda request: "test_user")
