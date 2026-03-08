"""
Tests for authentication endpoints: register, login, me, refresh, logout.

Covers TESTPLAN.md "Feature: Authentication".
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
)
from app.database import get_db
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import (
    create_refresh_token,
    validate_refresh_token,
)
from tests.conftest import TEST_PASSWORD, TestAsyncSession


# ---------------------------------------------------------------------------
# Refresh token fixtures (local to auth tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
async def refresh_token_str(db_session: AsyncSession, test_user: User) -> str:
    """A valid, unexpired refresh token for test_user persisted in the DB."""
    return await create_refresh_token(db=db_session, user_id=test_user.id)


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

    async def test_login_hides_auth_tokens_in_response_body(
        self, client, test_user: User
    ):
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "csrf_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["csrf_token"]) > 0

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


class TestAccessTokenCreation:
    """Access token expiration behavior."""

    def test_access_token_omits_exp_when_configured_non_expiring(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(settings, "access_token_expire_minutes", 0)

        token = create_access_token({"sub": "42"})
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},
        )

        assert payload["sub"] == "42"
        assert "exp" not in payload
        assert decode_access_token(token) == "42"

    def test_access_token_includes_exp_when_expiration_is_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(settings, "access_token_expire_minutes", 30)

        token = create_access_token({"sub": "42"})
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},
        )

        assert payload["sub"] == "42"
        assert "exp" in payload

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


class TestCsrfHelper:
    """GET /api/auth/csrf"""

    async def test_csrf_helper_returns_cookie_value_for_logged_in_user(
        self, client: AsyncClient, test_user: User
    ):
        login_response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        assert login_response.status_code == 200

        response = await client.get("/api/auth/csrf")
        assert response.status_code == 200
        assert response.json()["csrf_token"] == login_response.json()["csrf_token"]

    async def test_csrf_helper_requires_authentication(self, client: AsyncClient):
        response = await client.get("/api/auth/csrf")
        assert response.status_code == 401

    async def test_csrf_helper_returns_400_for_bearer_without_cookie(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        response = await client.get("/api/auth/csrf", headers=auth_headers)
        assert response.status_code == 400
        assert "CSRF cookie not found" in response.json()["detail"]


class TestLoginStoresRefreshToken:
    """POST /api/auth/login — refresh token persistence."""

    async def test_login_stores_refresh_token_in_db(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """The refresh token cookie issued by login must exist in the DB."""
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        refresh_token = response.cookies.get("refresh_token")
        assert refresh_token is not None

        row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        assert row is not None
        assert row.user_id == test_user.id


class TestRefresh:
    """POST /api/auth/refresh"""

    async def test_refresh_hides_auth_tokens_in_response_body(
        self, client: AsyncClient, refresh_token_str: str
    ):
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "csrf_token" in data
        assert data["token_type"] == "bearer"
        # New refresh token must differ from the consumed one (rotation)
        assert response.cookies["refresh_token"] != refresh_token_str

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

    async def test_refresh_sets_access_cookie_that_grants_access_to_me(
        self, client: AsyncClient, refresh_token_str: str
    ):
        """A refresh response should set an access cookie that works on /me."""
        refresh_response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )
        assert refresh_response.status_code == 200

        me_response = await client.get("/api/auth/me")
        assert me_response.status_code == 200

    async def test_refresh_concurrent_requests_only_one_succeeds(self):
        """Two concurrent refreshes for one token must not both succeed."""
        user_id: int | None = None
        refresh_token: str | None = None

        try:
            async with TestAsyncSession() as seed_session:
                suffix = uuid.uuid4().hex[:8]
                user = User(
                    username=f"race_user_{suffix}",
                    email=f"race_{suffix}@example.com",
                    hashed_password=get_password_hash(TEST_PASSWORD),
                )
                seed_session.add(user)
                await seed_session.flush()
                user_id = user.id
                refresh_token = await create_refresh_token(db=seed_session, user_id=user.id)
                await seed_session.commit()

            assert user_id is not None
            assert refresh_token is not None

            async def _override_get_db():
                async with TestAsyncSession() as session:
                    yield session

            app.dependency_overrides[get_db] = _override_get_db
            app.state.limiter.enabled = False

            transport = ASGITransport(app=app)
            async with (
                AsyncClient(transport=transport, base_url="http://test") as client_a,
                AsyncClient(transport=transport, base_url="http://test") as client_b,
            ):
                response_a, response_b = await asyncio.gather(
                    client_a.post(
                        "/api/auth/refresh",
                        json={"refresh_token": refresh_token},
                    ),
                    client_b.post(
                        "/api/auth/refresh",
                        json={"refresh_token": refresh_token},
                    ),
                )

            assert sorted([response_a.status_code, response_b.status_code]) == [200, 401]

            async with TestAsyncSession() as verify_session:
                rows = (
                    await verify_session.scalars(
                        select(RefreshToken).where(RefreshToken.user_id == user_id)
                    )
                ).all()
                assert len(rows) == 1
                assert rows[0].token != refresh_token
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.state.limiter.enabled = True

            if user_id is not None:
                async with TestAsyncSession() as cleanup_session:
                    await cleanup_session.execute(
                        delete(RefreshToken).where(RefreshToken.user_id == user_id)
                    )
                    await cleanup_session.execute(delete(User).where(User.id == user_id))
                    await cleanup_session.commit()

    async def test_refresh_rollback_preserves_old_token_on_rotation_failure(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """If rotation fails before commit, old token must remain valid in DB."""
        refresh_token = await create_refresh_token(db=db_session, user_id=test_user.id)
        await db_session.commit()

        async def _raise_during_rotation(*, db: AsyncSession, user_id: int) -> str:
            del db, user_id
            raise RuntimeError("forced refresh rotation failure")

        monkeypatch.setattr("app.api.auth.create_refresh_token", _raise_during_rotation)

        with pytest.raises(RuntimeError):
            await client.post(
                "/api/auth/refresh",
                json={"refresh_token": refresh_token},
            )

        # Roll back staged changes in this test transaction and verify old token remains.
        await db_session.rollback()
        row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        assert row is not None


class TestRefreshTokenHelperContract:
    """Contract tests for refresh-token helper transaction ownership."""

    async def test_validate_refresh_token_does_not_commit(
        self,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Expired-token cleanup is staged only; helper must not commit."""
        expired_token = "d" * 64
        db_session.add(
            RefreshToken(
                user_id=test_user.id,
                token=expired_token,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await db_session.flush()

        async def _unexpected_commit() -> None:
            raise AssertionError("validate_refresh_token must not call commit()")

        monkeypatch.setattr(db_session, "commit", _unexpected_commit)

        row = await validate_refresh_token(db=db_session, token=expired_token)
        assert row is None

        deleted_row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token == expired_token)
        )
        assert deleted_row is None


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

    async def test_login_clears_legacy_root_path_auth_cookies(
        self, client: AsyncClient, test_user: User
    ):
        """Login also expires legacy root-path auth cookies from older builds."""
        response = await client.post(
            "/api/auth/login",
            json={"username": test_user.username, "password": TEST_PASSWORD},
        )
        assert response.status_code == 200

        set_cookie_headers = response.headers.get_list("set-cookie")
        assert any(
            "access_token=" in header and "Path=/" in header and "Max-Age=0" in header
            for header in set_cookie_headers
        )
        assert any(
            "refresh_token=" in header and "Path=/" in header and "Max-Age=0" in header
            for header in set_cookie_headers
        )

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
