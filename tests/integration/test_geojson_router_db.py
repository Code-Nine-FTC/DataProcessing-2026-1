import pytest

pytestmark = pytest.mark.integration


class TestGeoJSONLayers:
    async def test_list_layers(self, test_client):
        resp = await test_client.get("/municipal/geojson/layers/")
        assert resp.status_code == 200
        data = resp.json()
        assert "layers" in data
        expected = {
            "municipios", "queimadas", "imoveis_rurais",
            "alertas_desmatamento", "terras_indigenas",
            "unidades_conservacao", "assentamentos", "quilombolas",
        }
        assert set(data["layers"]) == expected

    async def test_get_municipios_geojson(self, test_client):
        resp = await test_client.get("/municipal/geojson/layers/municipios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 3
        nomes = {f["properties"]["nome"] for f in data["features"]}
        assert "São José dos Campos" in nomes
        assert "Jacareí" in nomes
        assert "Caçapava" in nomes
        for f in data["features"]:
            assert "id" in f["properties"]
            assert "codigo_ibge" in f["properties"]
            assert f["properties"]["estado_sigla"] == "SP"
            assert f["geometry"]["type"] == "MultiPolygon"

    async def test_get_queimadas_geojson(self, test_client):
        resp = await test_client.get("/municipal/geojson/layers/queimadas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 5
        for f in data["features"]:
            assert f["geometry"]["type"] == "Point"
            props = f["properties"]
            assert "intensidade" in props
            assert "risco_fogo" in props
            assert "data_ocorrencia" in props
            assert "municipio" in props

    async def test_get_imoveis_rurais_geojson(self, test_client):
        resp = await test_client.get("/municipal/geojson/layers/imoveis_rurais")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 3
        nomes = {f["properties"]["nome"] for f in data["features"]}
        assert "Fazenda Teste Alpha" in nomes
        assert "Sitio Teste Beta" in nomes
        assert "Fazenda Teste Gamma" in nomes
        for f in data["features"]:
            assert f["geometry"]["type"] == "MultiPolygon"
            props = f["properties"]
            assert "codigo_car" in props
            assert "area_ha" in props
            assert "municipio" in props

    async def test_get_alertas_desmatamento_vazio(self, test_client):
        resp = await test_client.get(
            "/municipal/geojson/layers/alertas_desmatamento"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    async def test_get_layer_inexistente_404(self, test_client):
        resp = await test_client.get(
            "/municipal/geojson/layers/camada_invalida"
        )
        assert resp.status_code == 404

    async def test_get_municipios_filtrados_por_municipio_id(self, test_client):
        resp = await test_client.get(
            "/municipal/geojson/layers/municipios",
            params={"municipio_id": 3548708},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["nome"] == "São José dos Campos"

    async def test_get_queimadas_filtradas_por_municipio(self, test_client):
        resp = await test_client.get(
            "/municipal/geojson/layers/queimadas",
            params={"municipio_id": 3524402},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 2
        municipios = {f["properties"].get("municipio") for f in data["features"]}
        assert "Jacareí" in municipios

    async def test_get_imoveis_filtrados_por_municipio(self, test_client):
        resp = await test_client.get(
            "/municipal/geojson/layers/imoveis_rurais",
            params={"municipio_id": 3548708},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 1
        nomes = {f["properties"]["nome"] for f in data["features"]}
        assert "Fazenda Teste Alpha" in nomes
