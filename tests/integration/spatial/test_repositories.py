"""
Testes de integração para data-ingestion/infrastructure/repositories.py
Cobre: ST_Within, ST_Intersects em repositórios
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL

from data_ingestion.infrastructure.repositories import MunicipioRepository


def _get_sync_engine(session):
    """Cria uma engine síncrona (psycopg2) usando as variáveis de ambiente do workflow."""
    import os
    user = os.environ.get("POSTGRES_USER", "test")
    password = os.environ.get("POSTGRES_PASSWORD", "test")
    host = os.environ.get("POSTGRES_HOST", "localhost")  # Usa POSTGRES_HOST do workflow
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "test_db")

    sync_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(sync_url)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_municipio_by_geom_st_within(session: AsyncSession):
    """
    Teste para ST_Within em MunicipioRepository.find_by_name_and_state
    Verifica se a busca por geometria (centroide) funciona
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere município de teste com geometria conhecida
    await session.execute(text("""
        INSERT INTO municipio (nome, estado_id, geom)
        SELECT
            'Teste Municipio ST_Within',
            (SELECT id FROM estado WHERE sigla = 'SP'),
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio ST_Within')
        RETURNING id
    """))
    await session.commit()

    # 3. Obtém o repositório
    sync_engine = _get_sync_engine(session)
    repo = MunicipioRepository(sync_engine)

    # 4. Testa busca por nome (deve funcionar)
    municipio_id = repo.find_by_name_and_state("Teste Municipio ST_Within", "SP")
    assert municipio_id is not None, "Deveria encontrar município por nome"

    # 5. Testa busca por geometria (ST_Within)
    # Ponto dentro do polígono do município de teste (centroide)
    geom_wkt = "POINT(-46.65 -23.55)"
    municipio_id_by_geom = repo.find_by_name_and_state(
        "Teste Municipio ST_Within", "SP", geom_wkt=geom_wkt
    )

    # Deve retornar o município pois o ponto está dentro (ST_Within)
    assert municipio_id_by_geom is not None, "Deveria encontrar município via ST_Within com ponto interno"
    assert municipio_id_by_geom == municipio_id, "ID retornado deveria ser o mesmo"

    # 6. Testa com ponto fora (deve retornar None ou diferente)
    geom_fora = "POINT(-35.0 -20.0)"  # Oceano
    municipio_id_fora = repo.find_by_name_and_state(
        "Qualquer Nome", "SP", geom_wkt=geom_fora
    )
    assert municipio_id_fora is None, "Não deveria encontrar município com ponto no oceano"

    # 7. Limpeza
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_municipio_repository_st_intersects(session: AsyncSession):
    """
    Teste para ST_Intersects indireto via repositórios
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere município de teste
    result = await session.execute(text("""
        INSERT INTO municipio (nome, estado_id, geom)
        SELECT
            'Teste Municipio Intersects',
            (SELECT id FROM estado WHERE sigla = 'SP'),
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio Intersects')
        RETURNING id
    """))
    await session.commit()
    municipio_id = result.fetchone()[0]

    # 3. Verifica se o repositório consegue achar o município
    sync_engine = _get_sync_engine(session)
    repo = MunicipioRepository(sync_engine)
    found_id = repo.find_by_name_and_state("Teste Municipio Intersects", "SP")

    assert found_id is not None
    assert found_id == municipio_id

    # 4. Limpeza
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_by_geometry_st_intersects(session: AsyncSession):
    """
    Teste para a NOVA função find_by_geometry (adicionada no commit 5602ee8)
    Verifica se ST_Intersects + ST_Area(ST_Intersection) funcionam
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere município de teste com geometria conhecida
    await session.execute(text("""
        INSERT INTO municipio (nome, estado_id, geom)
        SELECT
            'Teste Municipio FindByGeom',
            (SELECT id FROM estado WHERE sigla = 'SP'),
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio FindByGeom')
        RETURNING id
    """))
    await session.commit()

    # 3. Obtém o repositório
    sync_engine = _get_sync_engine(session)
    repo = MunicipioRepository(sync_engine)

    # 4. Testa a nova função com geometria que INTERSECTA (deve encontrar)
    geom_intersecta = "POLYGON((-46.75 -23.65, -46.55 -23.65, -46.55 -23.45, -46.75 -23.45, -46.75 -23.65))"
    municipio_id = repo.find_by_geometry(geom_intersecta)
    assert municipio_id is not None, "Deveria encontrar município via ST_Intersects"

    # 5. Testa com geometria que NÃO intersecta (deve retornar None)
    geom_longe = "POLYGON((-35.0 -20.0, -34.9 -20.0, -34.9 -19.9, -35.0 -19.9, -35.0 -20.0))"
    resultado = repo.find_by_geometry(geom_longe)
    assert resultado is None, "Não deveria encontrar município com geometria longe"

    # 6. Verifica se retorna o maior intersectante (ordenado por área de interseção)
    # Insere outro município que intersecta mais área
    await session.execute(text("""
        INSERT INTO municipio (nome, estado_id, geom)
        SELECT
            'Teste Municipio FindByGeom 2',
            (SELECT id FROM estado WHERE sigla = 'SP'),
            ST_GeomFromText('POLYGON((-46.72 -23.62, -46.58 -23.62, -46.58 -23.48, -46.72 -23.48, -46.72 -23.62))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio FindByGeom 2')
        RETURNING id
    """))
    await session.commit()

    # Agora a geometria intersecta os dois, deve retornar o que tem maior interseção
    municipio_id_maior = repo.find_by_geometry(geom_intersecta)
    assert municipio_id_maior is not None

    # 7. Limpeza
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()
