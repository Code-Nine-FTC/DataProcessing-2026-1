import pytest
from sqlalchemy import text

class TestProximityQueries:
    @pytest.mark.asyncio
    async def test_distance_to_queimada(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography,
                ST_SetSRID(ST_MakePoint(-46.630, -23.580), 4326)::geography
            ) AS distancia
        """))
        row = result.scalar()
        assert row > 0

    @pytest.mark.asyncio
    async def test_within_radius(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_DWithin(
                ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)::geography,
                ST_SetSRID(ST_MakePoint(-46.630, -23.580), 4326)::geography,
                500
            ) AS within
        """))
        row = result.scalar()
        assert isinstance(row, bool)

    @pytest.mark.asyncio
    async def test_nearest_neighbors(self, db_session):
        # Exemplo: consulta KNN (K-Nearest Neighbors) usando <-> operador do PostGIS
        result = await db_session.execute(text("""
            SELECT id, geom
            FROM (
                VALUES (1, ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326)),
                       (2, ST_SetSRID(ST_MakePoint(-46.630, -23.580), 4326)),
                       (3, ST_SetSRID(ST_MakePoint(-46.635, -23.585), 4326))
            ) AS t(id, geom)
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(-46.632, -23.582), 4326)
            LIMIT 2
        """))
        rows = result.fetchall()
        assert len(rows) == 2
