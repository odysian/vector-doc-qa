import uuid

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_ip_key(request: Request) -> str:
    """
    Custom Rate Limit Key Function.

    Logic:
    1. If the IP is in the whitelist, return a RANDOM UUID.
       - This makes every request unique, so the rate limit counter
         never goes above 1.
    2. If normal user, return their IP address.
       - This applies the limit normally.
    """
    if not request.client:
        return "127.0.0.1"

    client_ip = request.client.host
    whitelist = [ip.strip() for ip in settings.whitelisted_ips]

    if client_ip in whitelist:

        return str(uuid.uuid4())
    return client_ip


limiter = Limiter(key_func=get_ip_key)

# Test rate limiter
# limiter = Limiter(key_func=lambda request: "test_user")
