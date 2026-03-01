"""Rate-limit identity tests for trusted and non-trusted proxy paths."""

import pytest
from starlette.requests import Request

from app.config import settings
from app.core.security import create_access_token
from app.utils.rate_limit import get_ip_key, get_user_or_ip_key


def _build_request(
    client_ip: str,
    *,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    """Create a minimal Request object for rate-limit key tests."""
    raw_headers: list[tuple[bytes, bytes]] = []
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))

    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        raw_headers.append((b"cookie", cookie_header.encode("latin-1")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset_rate_limit_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset rate-limit config knobs between tests."""
    monkeypatch.setattr(settings, "trusted_proxy_ips", [])
    monkeypatch.setattr(settings, "whitelisted_ips", [])


def test_get_ip_key_ignores_forwarded_headers_from_untrusted_peer() -> None:
    request = _build_request(
        "198.51.100.25",
        headers={"X-Forwarded-For": "203.0.113.77"},
    )

    assert get_ip_key(request) == "198.51.100.25"


def test_get_ip_key_uses_trusted_proxy_chain_and_ignores_left_spoof() -> None:
    settings.trusted_proxy_ips = ["10.0.0.0/8"]
    request = _build_request(
        "10.2.3.4",
        headers={"X-Forwarded-For": "1.1.1.1, 198.51.100.44, 10.9.9.9"},
    )

    assert get_ip_key(request) == "198.51.100.44"


def test_get_ip_key_does_not_whitelist_bypass_with_untrusted_spoof() -> None:
    settings.whitelisted_ips = ["203.0.113.9"]
    request = _build_request(
        "198.51.100.25",
        headers={"X-Forwarded-For": "203.0.113.9"},
    )

    assert get_ip_key(request) == "198.51.100.25"


def test_get_user_or_ip_key_keeps_user_key_for_bearer_token_behind_proxy() -> None:
    settings.trusted_proxy_ips = ["10.0.0.0/8"]
    token = create_access_token(data={"sub": "42"})
    request = _build_request(
        "10.2.3.4",
        headers={
            "X-Forwarded-For": "198.51.100.51",
            "Authorization": f"Bearer {token}",
        },
    )

    assert get_user_or_ip_key(request) == "user:42"


def test_get_user_or_ip_key_keeps_cookie_fallback_for_authenticated_user() -> None:
    token = create_access_token(data={"sub": "99"})
    request = _build_request("198.51.100.25", cookies={"access_token": token})

    assert get_user_or_ip_key(request) == "user:99"
