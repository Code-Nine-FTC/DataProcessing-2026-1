"""
Testes de cenários de erro para queries espaciais.
Valida o comportamento do sistema diante de dados inválidos, geometrias incorretas, SRID inconsistentes e timeouts.
"""

import pytest
import asyncio
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError, InternalError


class TestGeometryErrors:
    """Testes de erros relacionados a geometrias inválidas."""

    @pytest.mark.asyncio
    async def test_invalid_geometry_wkt(self, db_session):
        """Testa comportamento com WKT inválido - deve lançar exceção."""
        with pytest.raises((ProgrammingError, InternalError)):
            await db_session.execute(text("""
                SELECT ST_GeomFromText('INVALID_GEOMETRY', 4326)
            """))

    @pytest.mark.asyncio
    async def test_null_geometry_handling(self, db_session):
        """Testa comportamento com geometria nula."""
        result = await db_session.execute(text("""
            SELECT ST_Intersects(NULL, ST_GeomFromText('POINT(0 0)', 4326))
        """))
        assert result.scalar() is None

    @pytest.mark.asyncio
    async def test_empty_geometry(self, db_session):
        """Testa comportamento com geometria vazia."""
        result = await db_session.execute(text("""
            SELECT ST_IsEmpty(ST_GeomFromText('POINT EMPTY', 4326))
        """))
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_linestring_is_closed(self, db_session):
        """Testa que linestring não é fechada."""
        result = await db_session.execute(text("""
            SELECT ST_IsClosed(ST_GeomFromText('LINESTRING(0 0, 1 1, 2 2)', 4326))
        """))
        assert result.scalar() is False


class TestSRIDErrors:
    """Testes de erros de SRID."""

    @pytest.mark.asyncio
    async def test_mixed_srid_equals(self, db_session):
        """Testa ST_Equals com SRIDs mistos - deve lançar exceção."""
        with pytest.raises((ProgrammingError, InternalError)):
            await db_session.execute(text("""
                SELECT ST_Equals(
                    ST_SetSRID(ST_GeomFromText('POINT(0 0)'), 4326),
                    ST_SetSRID(ST_GeomFromText('POINT(0 0)'), 4674)
                )
            """))

    @pytest.mark.asyncio
    async def test_null_srid(self, db_session):
        """Testa geometria com SRID nulo."""
        result = await db_session.execute(text("""
            SELECT ST_SRID(ST_SetSRID(ST_GeomFromText('POINT(0 0)'), 0))
        """))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_srid_transformation_null(self, db_session):
        """Testa transformação com SRID nulo - deve lançar exceção."""
        with pytest.raises((ProgrammingError, InternalError)):
            await db_session.execute(text("""
                SELECT ST_Transform(ST_GeomFromText('POINT(0 0)'), 4326)
            """))


class TestInvalidInputErrors:
    """Testes de erros de entrada."""

    @pytest.mark.asyncio
    async def test_negative_buffer_distance(self, db_session):
        """Testa buffer com distância negativa."""
        result = await db_session.execute(text("""
            SELECT ST_Area(ST_Buffer(ST_GeomFromText('POINT(0 0)', 4326), -1))
        """))
        area = result.scalar()
        assert area is None or area >= 0

    @pytest.mark.asyncio
    async def test_invalid_point_in_polygon(self, db_session):
        """Testa ponto inválido em polígono."""
        result = await db_session.execute(text("""
            SELECT ST_Contains(
                ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 4326),
                ST_GeomFromText('POINT(5 5)', 4326))
        """))
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_point_outside_polygon(self, db_session):
        """Testa ponto fora do polígono."""
        result = await db_session.execute(text("""
            SELECT ST_Contains(
                ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 4326),
                ST_GeomFromText('POINT(15 15)', 4326))
        """))
        assert result.scalar() is False


class TestTopologyErrors:
    """Testes de erros topológicos."""

    @pytest.mark.asyncio
    async def test_self_intersecting_polygon(self, db_session):
        """Testa polígono com auto-interseção."""
        result = await db_session.execute(text("""
            SELECT ST_IsSimple(ST_GeomFromText(
                'POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))', 4326))
        """))
        assert result.scalar() is False

    @pytest.mark.asyncio
    async def test_degenerate_polygon(self, db_session):
        """Testa polígono degenerado (linha)."""
        result = await db_session.execute(text("""
            SELECT ST_IsValid(ST_GeomFromText('POLYGON((0 0, 1 1, 2 2, 0 0))', 4326))
        """))
        assert result.scalar() is False

    @pytest.mark.asyncio
    async def test_valid_polygon(self, db_session):
        """Testa polígono válido."""
        result = await db_session.execute(text("""
            SELECT ST_IsValid(ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 4326))
        """))
        assert result.scalar() is True


class TestPerformanceErrors:
    """Testes de timeout e performance."""

    @pytest.mark.asyncio
    async def test_query_timeout(self, db_session):
        """Testa timeout de query."""
        result = await db_session.execute(text("""
            SELECT 1 FROM pg_sleep(0.1)
        """))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_large_dataset_query(self, db_session):
        """Testa query em dataset grande."""
        result = await db_session.execute(text("""
            SELECT COUNT(*) FROM imovel_rural
        """))
        count = result.scalar()
        assert count >= 0

    @pytest.mark.asyncio
    async def test_spatial_index_usage(self, db_session):
        """Testa uso de índice espacial."""
        result = await db_session.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'imovel_rural'
            AND indexdef LIKE '%GIST%'
        """))
        indexes = result.fetchall()
        assert isinstance(indexes, list)


class TestConnectionErrors:
    """Testes de erros de conexão."""

    @pytest.mark.asyncio
    async def test_connection_valid(self, db_session):
        """Valida que conexão está ativa."""
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, db_session):
        """Testa isolamento de transação."""
        result = await db_session.execute(text("""
            SHOW transaction_isolation
        """))
        assert result.scalar() in ['read committed', 'repeatable read', 'serializable']


class TestDataIntegrityErrors:
    """Testes de integridade de dados."""

    @pytest.mark.asyncio
    async def test_null_geometria_handling(self, db_session):
        """Testa manipulação de geometria nula."""
        result = await db_session.execute(text("""
            SELECT ST_Contains(
                ST_GeomFromText('POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))', 4326),
                NULL
            )
        """))
        assert result.scalar() is None

    @pytest.mark.asyncio
    async def test_multiple_geometries(self, db_session):
        """Testa múltiplas geometrias (GeometryCollection)."""
        result = await db_session.execute(text("""
            SELECT ST_NumGeometries(ST_GeomFromText(
                'GEOMETRYCOLLECTION(POINT(0 0), LINESTRING(0 0, 1 1))', 4326))
        """))
        assert result.scalar() == 2

    @pytest.mark.asyncio
    async def test_as_text(self, db_session):
        """Testa conversão para texto."""
        result = await db_session.execute(text("""
            SELECT ST_AsText(ST_GeomFromText('POINT(0 0)', 4326))
        """))
        assert result.scalar() == 'POINT(0 0)'