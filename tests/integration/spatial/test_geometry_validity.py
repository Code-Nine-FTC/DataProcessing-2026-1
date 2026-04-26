import pytest
from sqlalchemy import text

class TestGeometryValidity:
    @pytest.mark.asyncio
    async def test_invalid_geometry_handling(self, db_session):
        # Geometria autointersectante (inválida)
        result = await db_session.execute(text("""
            SELECT ST_IsValid(ST_MakePolygon(ST_GeomFromText('LINESTRING(0 0, 1 1, 1 0, 0 1, 0 0)')))
        """))
        is_valid = result.scalar()
        assert is_valid is False
        # Corrige com ST_MakeValid
        result_valid = await db_session.execute(text("""
            SELECT ST_IsValid(ST_MakeValid(ST_MakePolygon(ST_GeomFromText('LINESTRING(0 0, 1 1, 1 0, 0 1, 0 0)'))))
        """))
        is_valid_after = result_valid.scalar()
        assert is_valid_after is True

    @pytest.mark.asyncio
    async def test_srid_consistency(self, db_session):
        result = await db_session.execute(text("""
            SELECT ST_SRID(ST_SetSRID(ST_MakePoint(-46.633, -23.583), 4326))
        """))
        srid = result.scalar()
        assert srid == 4326
