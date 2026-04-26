import pytest
from sqlalchemy import text

class TestContainsFunction:
    @pytest.mark.asyncio
    async def test_st_contains(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_Contains(
                ST_GeomFromText('POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))', 4326),
                ST_GeomFromText('POINT(1 1)', 4326)
            ) AS contains
        """))
        contains = result.scalar()
        assert contains is True
