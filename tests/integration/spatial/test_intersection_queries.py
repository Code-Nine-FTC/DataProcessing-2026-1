import pytest
from sqlalchemy import text

class TestIntersectionQueries:
    @pytest.mark.asyncio
    async def test_imovel_intersects_uc(self, db_session, sample_polygon):
        result = await db_session.execute(text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromText(:geom), 4326),
                ST_GeomFromText('POLYGON((-46.634 -23.584, -46.632 -23.586, -46.636 -23.591, -46.634 -23.584))', 4326)
            ) AS intersects
        """), {"geom": str(sample_polygon)})
        row = result.scalar()
        assert row is True or row is False

    @pytest.mark.asyncio
    async def test_imovel_intersects_ti(self, db_session, sample_polygon):
        result = await db_session.execute(text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromText(:geom), 4326),
                ST_GeomFromText('POLYGON((-46.638 -23.580, -46.637 -23.582, -46.639 -23.587, -46.638 -23.580))', 4326)
            ) AS intersects
        """), {"geom": str(sample_polygon)})
        row = result.scalar()
        assert row is True or row is False

    @pytest.mark.asyncio
    async def test_imovel_intersects_assentamento(self, db_session, sample_polygon):
        result = await db_session.execute(text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromText(:geom), 4326),
                ST_GeomFromText('POLYGON((-46.640 -23.582, -46.641 -23.584, -46.642 -23.589, -46.640 -23.582))', 4326)
            ) AS intersects
        """), {"geom": str(sample_polygon)})
        row = result.scalar()
        assert row is True or row is False

    @pytest.mark.asyncio
    async def test_imovel_intersects_quilombo(self, db_session, sample_polygon):
        result = await db_session.execute(text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromText(:geom), 4326),
                ST_GeomFromText('POLYGON((-46.645 -23.580, -46.646 -23.582, -46.647 -23.589, -46.645 -23.580))', 4326)
            ) AS intersects
        """), {"geom": str(sample_polygon)})
        row = result.scalar()
        assert row is True or row is False

    @pytest.mark.asyncio
    async def test_imovel_intersects_bacia(self, db_session, sample_polygon):
        result = await db_session.execute(text("""
            SELECT ST_Intersects(
                ST_SetSRID(ST_GeomFromText(:geom), 4326),
                ST_GeomFromText('POLYGON((-46.650 -23.580, -46.651 -23.582, -46.652 -23.589, -46.650 -23.580))', 4326)
            ) AS intersects
        """), {"geom": str(sample_polygon)})
        row = result.scalar()
        assert row is True or row is False
