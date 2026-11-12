
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient):
    payload = {
        "name": "Test Technologies",
        "slug": "test-technologies",
    }

    response = await client.post(
        "/v1/tenants",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test Technologies"
    assert data["slug"] == "test-technologies"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data



@pytest.mark.asyncio
async def test_duplicate_tenant_slug(client: AsyncClient):
    payload = {
        "name": "Acme Technologies",
        "slug": "acme-technologies",
    }

    # First request: create tenant
    first_response = await client.post(
        "/v1/tenants",
        json=payload,
    )

    assert first_response.status_code == 201

    # Second request: duplicate slug
    second_response = await client.post(
        "/v1/tenants",
        json=payload,
    )

    assert second_response.status_code == 409

    assert second_response.json()["detail"] == (
        "A tenant with this slug already exists"
    )

    # Third request: verify subsequent creation still works
    recovery_response = await client.post(
        "/v1/tenants",
        json={
            "name": "Nova Systems",
            "slug": "nova-systems",
        },
    )

    assert recovery_response.status_code == 201



@pytest.mark.asyncio
async def test_list_tenants(client: AsyncClient):
    # Create two tenants
    tenants = [
        {"name": "Alpha Systems", "slug": "alpha-systems"},
        {"name": "Beta Systems", "slug": "beta-systems"},
    ]

    for tenant in tenants:
        response = await client.post("/v1/tenants", json=tenant)
        assert response.status_code == 201

    # Retrieve tenant list
    response = await client.get(
        "/v1/tenants",
        params={"limit": 10, "offset": 0},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {tenant["slug"] for tenant in data} == {
        "alpha-systems",
        "beta-systems",
    }


