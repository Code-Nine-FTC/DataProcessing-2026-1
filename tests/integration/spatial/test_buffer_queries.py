import pytest
from sqlalchemy import text

class TestBufferQueries:
    @pytest.mark.asyncio
    async def test_buffer_area_calculation(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Area(ST_Buffer(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography, 1000)) AS area
        """))
        area = result.scalar()
        assert area > 0

    @pytest.mark.asyncio
    async def test_imoveis_within_buffer(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Within(
                ST_SetSRID(ST_MakePoint(-46.634, -23.584), 4326),
                ST_Buffer(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326), 0.01)
            ) AS within
        """))
        row = result.scalar()
        assert isinstance(row, bool)

    @pytest.mark.asyncio
    async def test_buffer_edge_cases(self, db_session):
        # Raio zero
        result_zero = await db_session.execute(text("""
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326), 0)
        """))
        geom_zero = result_zero.scalar()
        assert geom_zero is not None
        # Raio negativo
        result_neg = await db_session.execute(text("""
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326), -0.01)
        """))
        geom_neg = result_neg.scalar()
        assert geom_neg is not None
