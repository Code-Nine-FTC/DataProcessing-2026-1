"""
Testes de integração para endpoint POST /municipal/intersections
Cobre: ST_Intersects via endpoint HTTP (RF04 - interseção)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipal_intersections_encontra_imoveis(client: TestClient, session: AsyncSession):
    """
    Teste de integração para POST /municipal/intersections com geometria que intersecta imóveis
    Valida que o endpoint retorna imóveis rurais cuja geometria intersecta com o polígono enviado
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()

    # 2. Insere 2 imóveis rurais
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES
            ('Teste Intersection SP 1', 100.5,
             ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
             ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
             '{"tipo": "rural", "cultura": "soja"}'::jsonb),
            ('Teste Intersection SP 2', 75.3,
             ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
             ST_GeomFromText('POINT(-46.60 -23.50)', 4326),
             '{"tipo": "rural", "cultura": "milho"}'::jsonb)
    """))
    await session.commit()

    # 3. Envia POST com polígono que intersecta ambos os imóveis
    payload = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-46.75, -23.65],
                [-46.55, -23.65],
                [-46.55, -23.45],
                [-46.75, -23.45],
                [-46.75, -23.65]
            ]]
        }
    }
    response = client.post("/municipal/intersections", json=payload)

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 2

    nomes = [item["nome"] for item in data["data"]]
    assert "Teste Intersection SP 1" in nomes
    assert "Teste Intersection SP 2" in nomes

    for item in data["data"]:
        assert "id" in item
        assert "nome" in item
        assert "area_ha" in item
        assert "geom" in item
        assert item["geom"]["type"] in ["Polygon", "MultiPolygon"]
        assert "atributos_json" in item

    # 5. Limpa dados
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipal_intersections_ponto_unico(client: TestClient, session: AsyncSession):
    """
    Teste de integração para POST /municipal/intersections com ponto que intersecta apenas 1 imóvel
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Intersection Ponto',
            80.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            ST_GeomFromText('POINT(-46.60 -23.50)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    await session.commit()

    # 3. Envia POST com ponto dentro do imóvel
    payload = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-46.58, -23.48]
        }
    }
    response = client.post("/municipal/intersections", json=payload)

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["nome"] == "Teste Intersection Ponto"

    # 5. Limpa dados
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipal_intersections_sem_resultado(client: TestClient, session: AsyncSession):
    """
    Teste de integração para POST /municipal/intersections com geometria fora da área
    Valida que o endpoint retorna lista vazia quando nenhum imóvel intersecta
    """
    # 1. Envia POST com geometria no oceano (longe de qualquer imóvel)
    payload = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-35.0, -20.0],
                [-34.9, -20.0],
                [-34.9, -19.9],
                [-35.0, -19.9],
                [-35.0, -20.0]
            ]]
        }
    }
    response = client.post("/municipal/intersections", json=payload)

    # 2. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipal_intersections_body_invalido(client: TestClient, session: AsyncSession):
    """
    Teste de integração para POST /municipal/intersections com body inválido
    Valida que o endpoint retorna 422 quando o GeoJSON não é válido
    """
    # Envia POST com body sem campo geometry (inválido)
    payload = {
        "type": "Feature",
        "geometry": "nao_eh_um_dict"
    }
    response = client.post("/municipal/intersections", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipal_intersections_linestring(client: TestClient, session: AsyncSession):
    """
    Teste de integração para POST /municipal/intersections com LineString que intersecta imóvel
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Intersection Line',
            90.0,
            ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    await session.commit()

    # 3. Envia POST com LineString que atravessa o imóvel
    payload = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-46.72, -23.62],
                [-46.58, -23.48]
            ]
        }
    }
    response = client.post("/municipal/intersections", json=payload)

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) >= 1
    assert data["data"][0]["nome"] == "Teste Intersection Line"

    # 5. Limpa dados
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Intersection%'"))
    await session.commit()
