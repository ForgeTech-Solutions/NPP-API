"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient
from tests.conftest import auth_header


@pytest.mark.asyncio
class TestAuth:
    """Authentication tests."""

    async def test_login_success(self, client: AsyncClient, admin_user):
        """Test successful admin login."""
        response = await client.post("/auth/login", data={
            "username": "admin@test.com",
            "password": "AdminTest123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, admin_user):
        """Test login with wrong password."""
        response = await client.post("/auth/login", data={
            "username": "admin@test.com",
            "password": "WrongPassword!"
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent email."""
        response = await client.post("/auth/login", data={
            "username": "nobody@test.com",
            "password": "Test123!"
        })
        assert response.status_code == 401

    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected endpoint without token."""
        response = await client.get("/medicaments")
        assert response.status_code in [401, 403]  # 403 if no credentials header at all

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, admin_token):
        """Test accessing protected endpoint with valid token."""
        response = await client.get("/medicaments", headers=auth_header(admin_token))
        assert response.status_code == 200

    async def test_admin_endpoint_with_lecteur_token(self, client: AsyncClient, lecteur_token):
        """Test accessing admin endpoint with lecteur role."""
        response = await client.post(
            "/medicaments",
            headers=auth_header(lecteur_token),
            json={"code": "T001", "dci": "TEST", "nom_marque": "TEST BRAND",
                   "forme": "COMP", "dosage": "500MG", "conditionnement": "B/30",
                   "liste": "I", "p1": 100.0, "p2": 200.0, "obs": "N",
                   "type_medicament": "GE", "laboratoire": "LAB",
                   "pays_laboratoire": "ALGERIE",
                   "version_nomenclature": "2025-01"}
        )
        assert response.status_code == 403

    async def test_register_by_admin(self, client: AsyncClient, admin_token):
        """Test user registration by admin."""
        response = await client.post(
            "/auth/signup",
            headers=auth_header(admin_token),
            json={
                "email": "newuser@test.com",
                "password": "NewUser123!",
                "role": "LECTEUR"
            }
        )
        assert response.status_code == 201
