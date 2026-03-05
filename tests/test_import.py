"""Tests for import endpoints."""
import pytest
from httpx import AsyncClient
from tests.conftest import auth_header


@pytest.mark.asyncio
class TestImport:
    """Import endpoint tests."""

    async def test_preview_non_excel_file(self, client: AsyncClient, admin_token):
        """Test preview rejects non-Excel files."""
        response = await client.post(
            "/import/sheets/preview",
            headers=auth_header(admin_token),
            files={"file": ("test.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 400

    async def test_import_non_excel_file(self, client: AsyncClient, admin_token):
        """Test import rejects non-Excel files."""
        response = await client.post(
            "/import/nomenclature",
            headers=auth_header(admin_token),
            data={"version": "2025-01"},
            files={"file": ("test.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 400

    async def test_detect_duplicates(self, client: AsyncClient, admin_token):
        """Test duplicate detection endpoint."""
        response = await client.get(
            "/import/duplicates",
            headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_duplicates" in data
        assert "duplicates" in data

    async def test_clean_duplicates_dry_run(self, client: AsyncClient, admin_token):
        """Test clean duplicates in dry run mode."""
        response = await client.post(
            "/import/clean-duplicates?dry_run=true",
            headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
        assert "total_entries_deleted" in data
