"""
Testes de validação de schema contra dados reais (ou existentes) no banco.
Marcador: @pytest.mark.production_data — validam contratos de resposta,
não dependem de dados sintéticos específicos.

Objetivo: garantir que os endpoints RF04 retornam estruturas válidas
quando executados contra um banco com dados reais (staging/produção).
Estes testes não quebram se registros forem apagados, pois validam
tipos e campos, não valores específicos.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_sobreposicoes_areas_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de GET /analytics/sobreposicoes/areas
    contra dados reais existentes no banco. Se não houver dados, passa.
    """
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=uc&limite=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    d = data["data"]
    assert "tipo_area" in d
    assert "itens" in d
    assert "total" in d
    assert isinstance(d["tipo_area"], str)
    assert isinstance(d["itens"], list)
    assert isinstance(d["total"], int)
    assert d["total"] == len(d["itens"])

    if d["total"] > 0:
        item = d["itens"][0]
        required_fields = ["tipo_area", "imovel_id", "area_id", "area_intersecao_ha", "percentual_sobreposicao"]
        for field in required_fields:
            assert field in item, f"Campo '{field}' ausente no item de sobreposicao"


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_sobreposicoes_resumo_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de GET /analytics/sobreposicoes/resumo
    contra dados reais existentes no banco.
    """
    response = client.get("/analytics/sobreposicoes/resumo")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    resumo = data["data"]
    required_fields = [
        "imoveis_com_sobreposicao_uc",
        "imoveis_com_sobreposicao_ti",
        "imoveis_com_sobreposicao_quilombola",
        "imoveis_com_sobreposicao_assentamento",
        "total_imoveis",
    ]
    for field in required_fields:
        assert field in resumo, f"Campo '{field}' ausente no resumo"
        assert isinstance(resumo[field], int), f"Campo '{field}' deve ser int"


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_desmatamento_buffer_imoveis_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de GET /analytics/desmatamento/buffer-imoveis
    contra dados reais existentes no banco.
    """
    response = client.get("/analytics/desmatamento/buffer-imoveis?raio_km=5.0&limite=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    d = data["data"]
    assert "total" in d
    assert "itens" in d
    assert isinstance(d["total"], int)
    assert isinstance(d["itens"], list)

    if d["total"] > 0:
        item = d["itens"][0]
        required_fields = ["alerta_id", "imovel_id", "nome_imovel", "tipo_alerta", "area_buffer_ha"]
        for field in required_fields:
            assert field in item, f"Campo '{field}' ausente no item de buffer"


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_desmatamento_distancia_alertas_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de GET /analytics/desmatamento/distancia-alertas-imoveis
    contra dados reais existentes no banco.
    """
    response = client.get("/analytics/desmatamento/distancia-alertas-imoveis?raio_km=10.0&limite=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    d = data["data"]
    assert "total" in d
    assert "itens" in d

    if d["total"] > 0:
        item = d["itens"][0]
        required_fields = ["alerta_id", "imovel_id", "distancia_m"]
        for field in required_fields:
            assert field in item, f"Campo '{field}' ausente no item de distancia"
        assert isinstance(item["distancia_m"], (int, float)), "distancia_m deve ser numerico"


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_queimadas_distancia_imoveis_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de GET /analytics/queimadas/distancia-imoveis
    contra dados reais existentes no banco.
    """
    response = client.get("/analytics/queimadas/distancia-imoveis?raio_km=10.0&limite=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    d = data["data"]
    assert "total" in d
    assert "itens" in d

    if d["total"] > 0:
        item = d["itens"][0]
        required_fields = ["imovel_id", "evento_id", "distancia_m"]
        for field in required_fields:
            assert field in item, f"Campo '{field}' ausente no item de queimadas"


@pytest.mark.integration
@pytest.mark.production_data
async def test_schema_municipal_intersections_com_dados_existentes(client: TestClient, session: AsyncSession):
    """
    Valida o schema de resposta de POST /municipal/intersections
    contra dados reais existentes no banco. Envia um envelope cobrindo todo o Brasil.
    """
    payload = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-74.0, -34.0],
                [-34.0, -34.0],
                [-34.0, 5.0],
                [-74.0, 5.0],
                [-74.0, -34.0]
            ]]
        }
    }
    response = client.post("/municipal/intersections", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)

    if len(data["data"]) > 0:
        item = data["data"][0]
        required_fields = ["id", "nome", "area_ha", "geom", "atributos_json"]
        for field in required_fields:
            assert field in item, f"Campo '{field}' ausente no item de intersections"
