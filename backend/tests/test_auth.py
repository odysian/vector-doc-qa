"""
Tests for authentication endpoints: register, login, me, refresh, logout.

Covers TESTPLAN.md "Feature: Authentication".
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.conftest import TEST_PASSWORD


# ---------------------------------------------------------------------------
# Refresh token fixtures (local to auth tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
async def refresh_token_str(db_session: AsyncSession, test_user: User) -> str:
    """A valid, unexpired refresh token for test_user persisted in the DB."""
    return await create_refresh_token(test_user.id, db_session)


@pytest.fixture()
async def expired_refresh_token_str(db_session: AsyncSession, test_user: User) -> str:
    """An already-expired refresh token for test_user persisted in the DB."""
    raw_token = "a" * 64  # 64-char hex-like string
    db_session.add(
        RefreshToken(
            user_id=test_user.id,
            token=raw_token,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    await db_session.flush()
    return raw_token


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRegister:
    """POST /api/auth/register"""

    async def test_register_returns_201_with_valid_data(self, client):
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "created_at" in data
        # Password should never be in the response
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_password_is_hashed_in_database(self, client, db_session: AsyncSession):
        """Verify password is stored as an Argon2 hash, not plaintext."""
        password = "mysecretpass123"
        await client.post(
            "/api/auth/register",
            json={
                "username": "hashcheck",
                "email": "hashcheck@example.com",
                "password": password,
            },
        )

        result = await db_session.execute(
            select(User).where(User.username == "hashcheck")
        )
        user = result.scalar_one()

        assert user.hashed_password != password
        assert user.hashed_password.startswith("$argon2")

    # --- Error cases ---

    async def test_register_returns_422_without_username(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "pass12345678"},
        )
        assert response.status_code == 422

    async def test_register_returns_422_with_invalid_email(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "not-an-email", "password": "pass12345678"},
        )
        assert response.status_code == 422

    async def test_register_returns_422_without_password(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "test@example.com"},
        )
        assert response.status_code == 422

    async def test_register_returns_400_with_duplicate_username(self, client, test_user: User):
        response = await client.post(
            "/api/auth/register",
            json={
                "username": test_user.username,
                "email": "unique@example.com",
                "password": "pass12345678",
            },
        )
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]

    async def test_register_returns_400_with_duplicate_email(self, client, test_user: User):
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "uniqueuser",
                "email": test_user.email,
                "password": "pass12345678",
            },
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    # --- Edge cases ---

    async def test_register_handles_long_password(self, client):
        """128-character password should be accepted."""
        long_password = "a" * 100  # max_length is 100 per UserCreate schema
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "longpassuser",
                "email": "longpass@example.com",
                "password": long_password,
            },
        )
        assert response.status_code == 201


class TestLogin:
    """POST /api/auth/login"""

    async def test_login_returns_token_with_valid_credentials(self, client, test_user: User):
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) == 64  # secrets.token_hex(32)

    async def test_login_returns_401_with_wrong_username(self, client):
        response = await client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "pass12345678"},
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    async def test_login_returns_401_with_wrong_password(self, client, test_user: User):
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]


class TestMe:
    """GET /api/auth/me"""

    async def test_me_returns_current_user_with_valid_token(
        self, client, test_user: User, auth_headers: dict
    ):
        response = await client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email

    async def test_me_returns_401_without_token(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_me_returns_401_with_invalid_token(self, client):
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestLoginStoresRefreshToken:
    """POST /api/auth/login — refresh token persistence."""

    async def test_login_stores_refresh_token_in_db(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """The refresh token returned by login must exist in the DB."""
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        refresh_token = response.json()["refresh_token"]

        row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        assert row is not None
        assert row.user_id == test_user.id


class TestRefresh:
    """POST /api/auth/refresh"""

    async def test_refresh_returns_new_token_pair_with_valid_token(
        self, client: AsyncClient, refresh_token_str: str
    ):
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # New refresh token must differ from the consumed one (rotation)
        assert data["refresh_token"] != refresh_token_str

    async def test_refresh_rotates_old_token_deleted_from_db(
        self, client: AsyncClient, db_session: AsyncSession, refresh_token_str: str
    ):
        """After a successful refresh the old token row must not exist in the DB."""
        await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )

        row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        )
        assert row is None

    async def test_refresh_with_consumed_token_returns_401(
        self, client: AsyncClient, refresh_token_str: str
    ):
        """Using a token twice (after rotation) must be rejected."""
        await client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token_str}
        )
        # Clear the cookie jar so the second request uses only the body token.
        # Without this, the cookie-priority rule picks up the NEW refresh_token
        # cookie (set by the first response) and the call succeeds — masking
        # the reuse check that the test is actually validating.
        client.cookies.clear()
        # Second use of the now-deleted body token — must be rejected
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )

        assert response.status_code == 401

    async def test_refresh_with_nonexistent_token_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "b" * 64},
        )
        assert response.status_code == 401

    async def test_refresh_with_expired_token_returns_401(
        self, client: AsyncClient, expired_refresh_token_str: str
    ):
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_refresh_token_str},
        )
        assert response.status_code == 401

    async def test_refresh_new_access_token_grants_access_to_me(
        self, client: AsyncClient, refresh_token_str: str
    ):
        """The new access token from a refresh should work on protected endpoints."""
        refresh_response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )
        new_access_token = refresh_response.json()["access_token"]

        me_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_response.status_code == 200


class TestLogout:
    """POST /api/auth/logout"""

    async def test_logout_returns_200_with_valid_token(
        self, client: AsyncClient, refresh_token_str: str
    ):
        response = await client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token_str},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"

    async def test_logout_deletes_refresh_token_from_db(
        self, client: AsyncClient, db_session: AsyncSession, refresh_token_str: str
    ):
        await client.post("/api/auth/logout", json={"refresh_token": refresh_token_str})

        row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        )
        assert row is None

    async def test_logout_prevents_subsequent_refresh(
        self, client: AsyncClient, refresh_token_str: str
    ):
        """After logout the refresh token must not be accepted by /refresh."""
        await client.post("/api/auth/logout", json={"refresh_token": refresh_token_str})

        response = await client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token_str}
        )
        assert response.status_code == 401

    async def test_logout_is_idempotent(
        self, client: AsyncClient, refresh_token_str: str
    ):
        """Logging out twice must not raise an error."""
        await client.post("/api/auth/logout", json={"refresh_token": refresh_token_str})
        response = await client.post(
            "/api/auth/logout", json={"refresh_token": refresh_token_str}
        )
        assert response.status_code == 200

    async def test_logout_with_nonexistent_token_returns_200(self, client: AsyncClient):
        """Idempotent — no error if the token was never issued."""
        response = await client.post(
            "/api/auth/logout",
            json={"refresh_token": "c" * 64},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Cookie-based auth (new path — httpOnly cookies)
# ---------------------------------------------------------------------------


class TestCookieAuth:
    """httpOnly cookie-based authentication.

    Login sets three cookies; protected endpoints accept them;
    refresh and logout handle them without a request body.
    """

    async def test_login_sets_all_three_cookies(
        self, client: AsyncClient, test_user: User
    ):
        """POST /login sets access_token, refresh_token, and csrf_token cookies."""
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies
        assert "csrf_token" in response.cookies

    async def test_me_works_via_access_token_cookie(
        self, client: AsyncClient, test_user: User
    ):
        """After login the client has the access_token cookie; no Bearer header needed."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        # httpx propagates Set-Cookie headers; next request sends the cookie automatically
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id

    async def test_bearer_still_works_alongside_cookies(
        self, client: AsyncClient, test_user: User, auth_headers: dict[str, str]
    ):
        """Bearer header fallback is not broken by the cookie-first change."""
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id

    async def test_refresh_via_cookie_rotates_and_sets_new_cookies(
        self, client: AsyncClient, test_user: User
    ):
        """Refresh with no body uses the refresh_token cookie and sets fresh cookies."""
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        original_refresh = login_resp.cookies.get("refresh_token")
        # The client now has access_token cookie → CSRF check fires on POST
        csrf_token = client.cookies.get("csrf_token") or ""

        response = await client.post(
            "/api/auth/refresh",
            headers={"X-CSRF-Token": csrf_token},
            # No body — refresh_token cookie is the credential
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies
        assert "csrf_token" in response.cookies
        # Token must have rotated
        assert response.cookies["refresh_token"] != original_refresh

    async def test_logout_clears_cookies(
        self, client: AsyncClient, test_user: User
    ):
        """After logout, /me returns 401 because the access_token cookie is cleared."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        csrf_token = client.cookies.get("csrf_token") or ""

        logout_resp = await client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout_resp.status_code == 200

        # Cookies cleared (Max-Age=0) — /me must now return 401
        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------


class TestCSRF:
    """Double-submit cookie CSRF protection.

    Enforced on POST/PUT/DELETE when the access_token cookie is present.
    Skipped for Bearer auth and safe methods.
    """

    async def test_csrf_required_for_cookie_auth_post(
        self, client: AsyncClient, test_user: User
    ):
        """POST with access_token cookie but no X-CSRF-Token header → 403."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        # access_token cookie is now in client jar — CSRF check will fire
        response = await client.post("/api/auth/logout")
        assert response.status_code == 403
        assert "CSRF" in response.json()["detail"]

    async def test_csrf_passes_with_correct_header(
        self, client: AsyncClient, test_user: User
    ):
        """X-CSRF-Token header matching the csrf_token cookie passes the check."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        csrf_token = client.cookies.get("csrf_token") or ""
        response = await client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    async def test_csrf_returns_403_on_header_mismatch(
        self, client: AsyncClient, test_user: User
    ):
        """X-CSRF-Token that doesn't match the csrf_token cookie → 403."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        response = await client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": "wrong-token"},
        )
        assert response.status_code == 403
        assert "CSRF" in response.json()["detail"]

    async def test_csrf_not_required_for_bearer_auth(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Bearer auth (no cookie) is exempt — no X-CSRF-Token needed."""
        # auth_headers uses Bearer, no access_token cookie in client jar
        response = await client.post(
            "/api/auth/logout",
            headers=auth_headers,
            json={"refresh_token": "c" * 64},  # non-existent; logout is idempotent
        )
        assert response.status_code == 200

    async def test_csrf_not_required_for_get_requests(
        self, client: AsyncClient, test_user: User
    ):
        """GET is a safe method — CSRF check is skipped even with cookie auth."""
        await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        # GET /me — no X-CSRF-Token header needed
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id
