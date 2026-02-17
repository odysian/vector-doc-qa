"""
Tests for authentication endpoints: register, login, me.

Covers TESTPLAN.md "Feature: Authentication".
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import TEST_PASSWORD


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
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

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
