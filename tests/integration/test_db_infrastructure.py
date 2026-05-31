import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_db_connection(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_postgis_extension(db_session):
    result = await db_session.execute(text("SELECT PostGIS_Version()"))
    version = result.scalar_one()
    assert version is not None
    assert "3." in version


@pytest.mark.asyncio
async def test_seed_data_estado(db_session):
    result = await db_session.execute(text("SELECT COUNT(*) FROM estado"))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_seed_data_municipios(db_session):
    result = await db_session.execute(
        text("SELECT nome FROM municipio ORDER BY nome")
    )
    nomes = [row[0] for row in result]
    assert nomes == ["Caçapava", "Jacareí", "São José dos Campos"]


@pytest.mark.asyncio
async def test_seed_data_imoveis(db_session):
    result = await db_session.execute(text("SELECT COUNT(*) FROM imovel_rural"))
    assert result.scalar_one() == 3


@pytest.mark.asyncio
async def test_seed_data_queimadas(db_session):
    result = await db_session.execute(text("SELECT COUNT(*) FROM queimada_evento"))
    assert result.scalar_one() == 5


@pytest.mark.asyncio
async def test_seed_data_relacionamentos(db_session):
    result = await db_session.execute(text("SELECT COUNT(*) FROM rel_imovel_queimada"))
    assert result.scalar_one() == 5


@pytest.mark.asyncio
async def test_st_intersects_query(db_session):
    result = await db_session.execute(
        text("""
            SELECT i.nome_imovel
            FROM imovel_rural i
            WHERE ST_Intersects(
                i.geom,
                ST_GeomFromText('POLYGON((-46.0 -23.3, -45.8 -23.3, -45.8 -23.1, -46.0 -23.1, -46.0 -23.3))', 4326)
            )
        """)
    )
    imoveis = [row[0] for row in result]
    assert "Fazenda Teste Alpha" in imoveis


@pytest.mark.asyncio
async def test_queimadas_por_municipio(db_session):
    result = await db_session.execute(
        text("""
            SELECT m.nome, COUNT(qe.id) AS total
            FROM municipio m
            LEFT JOIN queimada_evento qe ON qe.municipio_id = m.id
            GROUP BY m.nome
            ORDER BY m.nome
        """)
    )
    rows = {row[0]: row[1] for row in result}
    assert rows["Caçapava"] == 1
    assert rows["Jacareí"] == 2
    assert rows["São José dos Campos"] == 2
