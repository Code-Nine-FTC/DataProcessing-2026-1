import pytest
from sqlalchemy import text

class TestAnalyticsQueries:
    @pytest.mark.asyncio
    async def test_desmatamento_buffer_imoveis(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography, 1000)
        """))
        geom = result.scalar()
        assert geom is not None

    @pytest.mark.asyncio
    async def test_desmatamento_distancia_alertas(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography,
                ST_SetSRID(ST_MakePoint(-46.630, -23.580), 4326)::geography
            )
        """))
        dist = result.scalar()
        assert dist > 0

    @pytest.mark.asyncio
    async def test_queimadas_distancia_imoveis(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography,
                ST_SetSRID(ST_MakePoint(-46.630, -23.580), 4326)::geography
            )
        """))
        dist = result.scalar()
        assert dist > 0
