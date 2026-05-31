import pytest

pytestmark = pytest.mark.integration


class TestSpatialValidation:
    async def test_health_spatial_ok(self, test_client):
        resp = await test_client.get("/health/spatial/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["auto_corrected"] is False

    async def test_health_spatial_auto_correct(self, test_client):
        resp = await test_client.get(
            "/health/spatial/", params={"auto_correct": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["auto_corrected"] is True
