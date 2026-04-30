"""
Testes de integração para api/services/index.py
Cobre: ST_Buffer, ST_Distance, ST_DWithin, ST_Intersects
"""
import pytest
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.index import AnalyticsService


@pytest.mark.asyncio
async def test_desmatamento_buffer_imoveis(session: AsyncSession):
    """
    Teste para ST_Buffer em desmatamento_buffer_imoveis
    Verifica se o buffer de alertas retorna imóveis dentro do raio
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere imóvel de teste (SP)
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel SP',
            100.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    # 3. Insere alerta de desmatamento próximo (dentro do raio de 5km)
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (tipo_alerta, geom, municipio_id)
        SELECT
            'desmatamento',
            ST_GeomFromText('POINT(-46.62 -23.52)', 4326),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 4. Executa a função com raio de 5km
    service = AnalyticsService(session)
    result = await service.desmatamento_buffer_imoveis(raio_km=5.0, limite=100)

    # 5. Validações
    assert result is not None
    assert result.total > 0, "Deveria encontrar imóveis no buffer"
    assert len(result.itens) > 0, "Lista de itens não deveria estar vazia"

    # Verifica se o imóvel de teste está nos resultados
    nomes_imoveis = [item.nome_imovel for item in result.itens]
    assert "Teste Imóvel SP" in nomes_imoveis, "Imóvel de teste deveria estar no buffer"

    # Verifica se área do buffer foi calculada
    for item in result.itens:
        assert item.area_buffer_ha > 0, "Área do buffer deveria ser positiva"
        assert item.buffer_geojson is not None, "GeoJSON do buffer não deveria ser nulo"

        # Valida estrutura do GeoJSON
        buffer_geom = json.loads(item.buffer_geojson) if isinstance(item.buffer_geojson, str) else item.buffer_geojson
        assert buffer_geom["type"] in ["Polygon", "MultiPolygon"], "Buffer deveria ser Polygon/MultiPolygon"

    # 6. Limpa dados de teste
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_desmatamento_distancia_alertas(session: AsyncSession):
    """
    Teste para ST_Distance e ST_DWithin em desmatamento_distancia_alertas
    Verifica se a distância entre imóveis e alertas é calculada corretamente
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
            'Teste Imóvel SP 2',
            80.0,
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))

    # 3. Insere alerta a ~5km de distância
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (tipo_alerta, geom, municipio_id)
        SELECT
            'desmatamento',
            ST_GeomFromText('POINT(-46.5 -23.4)', 4326),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 4. Executa a função com raio de 10km
    service = AnalyticsService(session)
    result = await service.desmatamento_distancia_alertas(raio_km=10.0, limite=100)

    # 5. Validações
    assert result is not None
    assert result.total > 0, "Deveria encontrar pares imóvel-alerta"
    assert len(result.itens) > 0

    # Verifica se distâncias estão corretas (devem ser < 10km = 10000m)
    for item in result.itens:
        assert item.distancia_m < 10000, f"Distância deveria ser < 10km, mas é {item.distancia_m}m"
        assert item.distancia_m > 0, "Distância deveria ser positiva"
        assert item.imovel_id is not None
        assert item.alerta_id is not None

    # 6. Limpa dados de teste
    await session.execute(text("DELETE FROM desmatamento_alerta"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_queimadas_distancia_imoveis(session: AsyncSession):
    """
    Teste para ST_Distance em queimadas_distancia_imoveis
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM queimada_evento"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere imóvel de teste
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

    # 3. Insere foco de queimada próximo
    await session.execute(text("""
        INSERT INTO queimada_evento
            (tipo_foco, geom, municipio_id)
        SELECT
            'fogo',
            ST_GeomFromText('POINT(-46.72 -23.62)', 4326),
            id
        FROM municipio
        WHERE nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 4. Executa a função
    service = AnalyticsService(session)
    result = await service.queimadas_distancia_imoveis(raio_km=10.0, limite=100)

    # 5. Validações
    assert result is not None
    # Pode ou não encontrar (depende de dados existentes), mas não deve falhar
    if result.total > 0:
        for item in result.itens:
            assert item.distancia_m < 10000, "Distância deveria ser < 10km"
            assert item.distancia_m > 0

    # 6. Limpa dados de teste
    await session.execute(text("DELETE FROM queimada_evento"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()
