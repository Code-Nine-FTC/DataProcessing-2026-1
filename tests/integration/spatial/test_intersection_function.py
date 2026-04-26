import pytest
from sqlalchemy import text

class TestIntersectionFunction:
    @pytest.mark.asyncio
    async def test_st_intersection(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_AsText(ST_Intersection(
                ST_GeomFromText('POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))', 4326),
                ST_GeomFromText('POLYGON((1 1, 3 1, 3 3, 1 3, 1 1))', 4326)
            )) AS intersection
        """))
        intersection = result.scalar()
        # Deve retornar um polígono de interseção
        assert intersection is not None
        assert 'POLYGON' in intersection or 'GEOMETRYCOLLECTION' in intersection
