import pytest

pytestmark = pytest.mark.integration


class TestMunicipalRouter:
    async def test_get_all_municipios(self, test_client):
        resp = await test_client.get("/municipal/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        nomes = {m["nome"] for m in data}
        assert "São José dos Campos" in nomes
        assert "Jacareí" in nomes
        assert "Caçapava" in nomes
        for m in data:
            assert "id" in m
            assert "codigo_ibge" in m
            assert m["estado_sigla"] == "SP"
            assert "geom" in m

    async def test_get_municipio_por_id(self, test_client):
        resp = await test_client.get("/municipal/3548708")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        mun = data[0]
        assert mun["id"] == 3548708
        assert mun["nome"] == "São José dos Campos"
        assert mun["codigo_ibge"] == "3548708"
        assert mun["estado_sigla"] == "SP"

    async def test_get_municipio_inexistente_retorna_vazio(self, test_client):
        resp = await test_client.get("/municipal/99999")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == []

    async def test_search_municipio_por_nome_parcial(self, test_client):
        resp = await test_client.get(
            "/municipal/search", params={"q": "jacarei"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["nome"] == "Jacareí"
        assert data[0]["codigo_ibge"] == "3524402"
        assert data[0]["estado_sigla"] == "SP"

    async def test_search_municipio_sem_resultados(self, test_client):
        resp = await test_client.get(
            "/municipal/search", params={"q": "ZZZZZ"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_search_municipio_por_estado(self, test_client):
        resp = await test_client.get(
            "/municipal/search", params={"estado_sigla": "SP"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        for m in data:
            assert m["estado_sigla"] == "SP"

    async def test_post_intersections_com_polygon(self, test_client):
        payload = {
            "type": "Polygon",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-45.95, -23.22],
                    [-45.90, -23.22],
                    [-45.90, -23.18],
                    [-45.95, -23.18],
                    [-45.95, -23.22],
                ]],
            },
        }
        resp = await test_client.post("/municipal/intersections", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        nomes = {i["nome"] for i in data}
        assert "Fazenda Teste Alpha" in nomes

    async def test_post_intersections_sem_resultados(self, test_client):
        payload = {
            "type": "Polygon",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-50.0, -30.0],
                    [-49.0, -30.0],
                    [-49.0, -29.0],
                    [-50.0, -29.0],
                    [-50.0, -30.0],
                ]],
            },
        }
        resp = await test_client.post("/municipal/intersections", json=payload)
        assert resp.status_code == 200
        assert resp.json()["data"] == []
