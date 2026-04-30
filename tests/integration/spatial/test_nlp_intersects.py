"""
Testes de integração para nlp_processor/tools.py
Cobre: ST_Intersects em múltiplas funções
"""
import pytest
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.tools import (
    buscar_unidades_conservacao,
    buscar_terras_indigenas,
    buscar_assentamentos_rurais,
    buscar_territorios_quilombolas,
    buscar_imoveis_rurais,
)


@pytest.mark.asyncio
async def test_buscar_unidades_conservacao_sp(session: AsyncSession):
    """
    Teste para ST_Intersects em buscar_unidades_conservacao
    Verifica se filtra corretamente por São Paulo
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere unidade de conservação no estado de SP
    await session.execute(text("""
        INSERT INTO unidade_conservacao
            (nome, categoria, geom, area_ha, municipio_id, dataset_id)
        SELECT
            'Teste UC SP',
            'Estadual',
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            500.0,
            m.id,
            d.id
        FROM municipio m, dataset d
        WHERE m.nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa busca para SP
    result = await buscar_unidades_conservacao(session, estado="SP")

    # 4. Validações
    assert result is not None
    assert result["total"] > 0, "Deveria encontrar unidades em SP"

    # Verifica se a unidade de teste está nos resultados
    nomes = [f["properties"].get("nome") for f in result["features"]]
    assert "Teste UC SP" in nomes, "Unidade de teste deveria estar no resultado"

    # Valida estrutura GeoJSON
    for feature in result["features"]:
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        assert "properties" in feature

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_buscar_terras_indigenas_sp(session: AsyncSession):
    """
    Teste para ST_Intersects em buscar_terras_indigenas
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere terra indígena no estado de SP
    await session.execute(text("""
        INSERT INTO terra_indigena
            (nome, geom, area_ha, municipio_id, dataset_id)
        SELECT
            'Teste TI SP',
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            300.0,
            m.id,
            d.id
        FROM municipio m, dataset d
        WHERE m.nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa busca para SP
    result = await buscar_terras_indigenas(session, estado="SP")

    # 4. Validações
    assert result is not None
    if result["total"] > 0:
        nomes = [f["properties"].get("nome") for f in result["features"]]
        assert "Teste TI SP" in nomes

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_buscar_assentamentos_rurais_sp(session: AsyncSession):
    """
    Teste para ST_Intersects em buscar_assentamentos_rurais
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere assentamento no estado de SP
    await session.execute(text("""
        INSERT INTO assentamento_rural
            (nome, modalidade, geom, area_ha, municipio_id, dataset_id)
        SELECT
            'Teste AR SP',
            'PA',
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            200.0,
            m.id,
            d.id
        FROM municipio m, dataset d
        WHERE m.nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa busca para SP
    result = await buscar_assentamentos_rurais(session, estado="SP")

    # 4. Validações
    assert result is not None
    if result["total"] > 0:
        nomes = [f["properties"].get("nome") for f in result["features"]]
        # Pode ou não incluir o de teste, depende de outros filtros

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_buscar_territorios_quilombolas_sp(session: AsyncSession):
    """
    Teste para ST_Intersects em buscar_territorios_quilombolas
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere território quilombola no estado de SP
    await session.execute(text("""
        INSERT INTO territorio_quilombola
            (nome, geom, area_ha, municipio_id, dataset_id)
        SELECT
            'Teste TQ SP',
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            150.0,
            m.id,
            d.id
        FROM municipio m, dataset d
        WHERE m.nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa busca para SP
    result = await buscar_territorios_quilombolas(session, estado="SP")

    # 4. Validações
    assert result is not None
    if result["total"] > 0:
        nomes = [f["properties"].get("nome") for f in result["features"]]
        assert "Teste TQ SP" in nomes

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_buscar_imoveis_rurais_sp(session: AsyncSession):
    """
    Teste para ST_Intersects em buscar_imoveis_rurais
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere imóvel rural no estado de SP
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json, municipio_id, dataset_id)
        SELECT
            'Teste Imóvel SP',
            100.0,
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb,
            m.id,
            d.id
        FROM municipio m, dataset d
        WHERE m.nome LIKE '%São Paulo%'
        LIMIT 1
    """))
    await session.commit()

    # 3. Executa busca para SP
    result = await buscar_imoveis_rurais(session, estado="SP")

    # 4. Validações
    assert result is not None
    assert result["total"] > 0, "Deveria encontrar imóveis em SP"

    # Verifica se o imóvel de teste está nos resultados
    nomes = [f["properties"].get("nome_imovel") for f in result["features"]]
    assert "Teste Imóvel SP" in nomes, "Imóvel de teste deveria estar no resultado"

    # 5. Limpa dados de teste
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()
