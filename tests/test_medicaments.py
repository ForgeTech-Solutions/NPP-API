"""Tests for medicaments CRUD endpoints."""
import pytest
from httpx import AsyncClient
from tests.conftest import auth_header


SAMPLE_MEDICAMENT = {
    "code": "1001",
    "dci": "PARACETAMOL",
    "nom_marque": "DOLIPRANE",
    "forme": "COMPRIME",
    "dosage": "500MG",
    "conditionnement": "B/30",
    "liste": "I",
    "p1": "HOP",
    "p2": "OFF",
    "obs": "N",
    "type_medicament": "GE",
    "laboratoire": "SANOFI",
    "pays_laboratoire": "FRANCE",
    "statut": "F",
    "version_nomenclature": "2025-01",
    "categorie": "NOMENCLATURE"
}


@pytest.mark.asyncio
class TestMedicamentsCRUD:
    """CRUD operation tests."""

    async def test_create_medicament(self, client: AsyncClient, admin_token):
        """Test creating a new medicament."""
        response = await client.post(
            "/medicaments",
            headers=auth_header(admin_token),
            json=SAMPLE_MEDICAMENT
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "1001"
        assert data["dci"] == "PARACETAMOL"
        assert data["categorie"] == "NOMENCLATURE"

    async def test_list_medicaments(self, client: AsyncClient, admin_token):
        """Test listing medicaments with pagination."""
        # Create a medicament first
        await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        
        response = await client.get("/medicaments", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert "has_next" in data
        assert "has_previous" in data
        assert data["total"] >= 1

    async def test_get_medicament_by_id(self, client: AsyncClient, admin_token):
        """Test retrieving a single medicament by ID."""
        # Create
        create_resp = await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        med_id = create_resp.json()["id"]
        
        response = await client.get(f"/medicaments/{med_id}", headers=auth_header(admin_token))
        assert response.status_code == 200
        assert response.json()["id"] == med_id

    async def test_get_nonexistent_medicament(self, client: AsyncClient, admin_token):
        """Test 404 for nonexistent medicament."""
        response = await client.get("/medicaments/99999", headers=auth_header(admin_token))
        assert response.status_code == 404

    async def test_update_medicament(self, client: AsyncClient, admin_token):
        """Test updating a medicament."""
        create_resp = await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        med_id = create_resp.json()["id"]
        
        response = await client.put(
            f"/medicaments/{med_id}",
            headers=auth_header(admin_token),
            json={"nom_marque": "DOLIPRANE FORTE"}
        )
        assert response.status_code == 200
        assert response.json()["nom_marque"] == "DOLIPRANE FORTE"

    async def test_delete_medicament(self, client: AsyncClient, admin_token):
        """Test soft-deleting a medicament."""
        create_resp = await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        med_id = create_resp.json()["id"]
        
        response = await client.delete(f"/medicaments/{med_id}", headers=auth_header(admin_token))
        assert response.status_code == 204
        
        # Should no longer be found
        get_resp = await client.get(f"/medicaments/{med_id}", headers=auth_header(admin_token))
        assert get_resp.status_code == 404


@pytest.mark.asyncio
class TestSearchAndFilter:
    """Search and filter tests."""

    async def _create_samples(self, client, token):
        """Helper to create sample data."""
        samples = [
            {**SAMPLE_MEDICAMENT, "code": "2001", "dci": "AMOXICILLINE", "nom_marque": "AMOXIL",
             "laboratoire": "GSK", "pays_laboratoire": "ROYAUME-UNI", "type_medicament": "RE"},
            {**SAMPLE_MEDICAMENT, "code": "2002", "dci": "PARACETAMOL", "nom_marque": "EFFERALGAN",
             "laboratoire": "UPSA", "pays_laboratoire": "FRANCE", "type_medicament": "GE"},
            {**SAMPLE_MEDICAMENT, "code": "2003", "dci": "IBUPROFENE", "nom_marque": "ADVIL",
             "laboratoire": "PFIZER", "pays_laboratoire": "ETATS-UNIS", "type_medicament": "RE",
             "categorie": "NON_RENOUVELE"},
        ]
        for s in samples:
            await client.post("/medicaments", headers=auth_header(token), json=s)

    async def test_full_text_search(self, client: AsyncClient, admin_token):
        """Test full-text search across multiple fields."""
        await self._create_samples(client, admin_token)
        
        response = await client.get("/medicaments?q=AMOXICILLINE", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any("AMOXICILLINE" in item["dci"] for item in data["items"])

    async def test_filter_by_categorie(self, client: AsyncClient, admin_token):
        """Test filtering by categorie."""
        await self._create_samples(client, admin_token)
        
        response = await client.get("/medicaments?categorie=NON_RENOUVELE", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["categorie"] == "NON_RENOUVELE"

    async def test_filter_by_type(self, client: AsyncClient, admin_token):
        """Test filtering by type."""
        await self._create_samples(client, admin_token)
        
        response = await client.get("/medicaments?type=RE", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["type_medicament"] == "RE"

    async def test_sort_by_dci(self, client: AsyncClient, admin_token):
        """Test sorting by DCI ascending."""
        await self._create_samples(client, admin_token)
        
        response = await client.get("/medicaments?sort_by=dci&order=asc", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        dcis = [item["dci"] for item in data["items"]]
        assert dcis == sorted(dcis)


@pytest.mark.asyncio
class TestStatisticsAndDashboard:
    """Statistics and dashboard tests."""

    async def test_statistics(self, client: AsyncClient, admin_token):
        """Test statistics endpoint."""
        await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        
        response = await client.get("/medicaments/statistiques", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "par_laboratoire" in data
        assert "par_pays" in data
        assert "par_type" in data

    async def test_dashboard(self, client: AsyncClient, admin_token):
        """Test dashboard endpoint."""
        await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        
        response = await client.get("/medicaments/dashboard", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert "total_medicaments" in data
        assert "top_10_laboratoires" in data
        assert "top_10_pays" in data


@pytest.mark.asyncio
class TestExportAndDCI:
    """Export and DCI grouping tests."""

    async def test_export_csv(self, client: AsyncClient, admin_token):
        """Test CSV export."""
        await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        
        response = await client.get("/medicaments/export", headers=auth_header(admin_token))
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        content = response.text
        assert "PARACETAMOL" in content

    async def test_par_dci(self, client: AsyncClient, admin_token):
        """Test grouping by DCI."""
        await client.post("/medicaments", headers=auth_header(admin_token), json=SAMPLE_MEDICAMENT)
        
        response = await client.get("/medicaments/par-dci/PARACETAMOL", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert data["dci"] == "PARACETAMOL"
        assert data["total"] >= 1

    async def test_par_dci_not_found(self, client: AsyncClient, admin_token):
        """Test DCI grouping with nonexistent DCI."""
        response = await client.get("/medicaments/par-dci/INEXISTANT", headers=auth_header(admin_token))
        assert response.status_code == 404
