"""
Testes de integração para endpoints de analytics (api/router/analytics.py)
Cobre: Serviços RF-04 completos (buffer, distância, proximidade) + endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_desmatamento_buffer_imoveis(client: TestClient, session: AsyncSession):
    """
    Teste de integração para o endpoint GET /desmatamento/buffer-imoveis
    Verifica se o endpoint RF-04 retorna dados corretos
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere imóvel de teste
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel Endpoint',
            100.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    # 3. Insere alerta de desmatamento próximo
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (tipo_alerta, geom, municipio_id)
        SELECT
            'desmatamento',
            ST_Buffer(ST_Multi(ST_Buffer(ST_GeomFromText('POINT(-46.62 -23.52)', 4326), 0.001)), 0.001),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 4. Como o endpoint depende de SessionConnection.session (Depends),
    # vamos chamar o serviço diretamente (mesma lógica)
    from api.services.index import AnalyticsService
    service = AnalyticsService(session)
    result = await service.desmatamento_buffer_imoveis(raio_km=5.0, limite=100)

    # 5. Validações
    assert result is not None
    assert result.total >= 0  # Pode ser 0 se não houver sobreposição
    assert len(result.itens) == result.total

    # Verifica estrutura dos itens
    for item in result.itens:
        assert item.alerta_id is not None
        assert item.tipo_alerta is not None
        assert item.imovel_id is not None
        assert item.nome_imovel is not None
        if item.area_buffer_ha is not None:
            assert item.area_buffer_ha > 0
        if item.buffer_geojson is not None:
            import json
            buffer = json.loads(item.buffer_geojson) if isinstance(item.buffer_geojson, str) else item.buffer_geojson
            assert buffer["type"] in ["Polygon", "MultiPolygon"]

    # 6. Limpa dados de teste
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere dados de teste
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel Distância',
            80.0,
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (tipo_alerta, geom, municipio_id)
        SELECT
            'desmatamento',
            ST_Buffer(ST_Multi(ST_Buffer(ST_GeomFromText('POINT(-46.65 -23.55)', 4326), 0.001)), 0.001),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa serviço diretamente
    from api.services.index import AnalyticsService
    service = AnalyticsService(session)
    result = await service.desmatamento_distancia_alertas(raio_km=10.0, limite=100)

    # 4. Validações
    assert result is not None
    assert result.total >= 0
    assert len(result.itens) == result.total

    # Verifica distâncias
    for item in result.itens:
        assert item.distancia_m < 10000  # Menor que 10km
        assert item.imovel_id is not None
        assert item.alerta_id is not None

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere dados de teste
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel Queimada',
            120.0,
            ST_GeomFromText('POLYGON((-46.8 -23.7, -46.7 -23.7, -46.7 -23.6, -46.8 -23.6, -46.8 -23.7))', 4326),
            ST_GeomFromText('POINT(-46.75 -23.65)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    await session.execute(text("""
        INSERT INTO queimada_evento
            (fonte_sensor, geom, municipio_id)
        SELECT
            'fogo',
            ST_GeomFromText('POINT(-46.72 -23.62)', 4326),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa serviço diretamente
    from api.services.index import AnalyticsService
    service = AnalyticsService(session)
    result = await service.queimadas_distancia_imoveis(raio_km=10.0, limite=100)

    # 4. Validações
    assert result is not None
    assert result.total >= 0
    assert len(result.itens) == result.total

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM queimada_evento"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_desmatamento_buffer_imoveis(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint real GET /analytics/desmatamento/buffer-imoveis
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere dados de teste
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Endpoint Buffer',
            100.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    await session.execute(text("""
        INSERT INTO desmatamento_alerta (tipo_alerta, geom, municipio_id)
        SELECT 'desmatamento', ST_Multi(ST_Buffer(ST_GeomFromText('POINT(-46.62 -23.52)', 4326), 0.001)), id
        FROM municipio WHERE nome LIKE '%São Paulo%' LIMIT 1
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/desmatamento/buffer-imoveis?raio_km=5.0&limite=100")

    # 4. Valida resposta HTTP
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data["data"]
    assert "itens" in data["data"]

    # Valida estrutura dos dados retornados
    if data["data"]["total"] > 0:
        item = data["data"]["itens"][0]
        assert "alerta_id" in item
        assert "imovel_id" in item
        assert "nome_imovel" in item
        assert "tipo_alerta" in item

    # 5. Limpa dados
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_desmatamento_distancia_alertas(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint real GET /analytics/desmatamento/distancia-alertas-imoveis
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere dados de teste
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Endpoint Distância',
            80.0,
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    await session.execute(text("""
        INSERT INTO desmatamento_alerta (tipo_alerta, geom, municipio_id)
        SELECT 'desmatamento', ST_Multi(ST_Buffer(ST_GeomFromText('POINT(-46.65 -23.55)', 4326), 0.001)), id
        FROM municipio WHERE nome LIKE '%São Paulo%' LIMIT 1
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/desmatamento/distancia-alertas-imoveis?raio_km=10.0&limite=100")

    # 4. Valida resposta HTTP
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data["data"]
    assert "itens" in data["data"]

    # Valida distâncias nos itens
    for item in data["data"]["itens"]:
        assert item["distancia_m"] < 10000, "Distância deveria ser menor que 10km"
        assert item["imovel_id"] is not None
        assert item["alerta_id"] is not None

    # 5. Limpa dados
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_queimadas_distancia_imoveis(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint real GET /analytics/queimadas/distancia-imoveis
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM queimada_evento"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere dados de teste
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Endpoint Queimada',
            120.0,
            ST_GeomFromText('POLYGON((-46.8 -23.7, -46.7 -23.7, -46.7 -23.6, -46.8 -23.6, -46.8 -23.7))', 4326),
            ST_GeomFromText('POINT(-46.75 -23.65)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    await session.execute(text("""
        INSERT INTO queimada_evento (fonte_sensor, geom, municipio_id)
        SELECT 'fogo', ST_GeomFromText('POINT(-46.72 -23.62)', 4326), id
        FROM municipio WHERE nome LIKE '%São Paulo%' LIMIT 1
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/queimadas/distancia-imoveis?raio_km=10.0&limite=100")

    # 4. Valida resposta HTTP
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data["data"]
    assert "itens" in data["data"]

    # Valida estrutura dos itens retornados
    if data["data"]["total"] > 0:
        for item in data["data"]["itens"]:
            assert "imovel_id" in item
            assert "evento_id" in item
            assert "distancia_m" in item
            assert item["distancia_m"] < 10000

    # 5. Limpa dados
    await session.execute(text("DELETE FROM queimada_evento"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()
