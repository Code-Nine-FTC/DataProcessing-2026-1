import pytest
from sqlalchemy import text
import time

class TestPerformance:
    @pytest.mark.asyncio
    async def test_spatial_index_usage(self, db_session):
        # Exemplo: verifica se o plano de execução usa GIST
        result = await db_session.execute(text("""
            EXPLAIN ANALYZE SELECT * FROM rel_imovel_queimada WHERE geom && ST_MakeEnvelope(-47, -24, -46, -23, 4326)
        """))
        plan = result.fetchall()[0][0]
        assert 'Bitmap Index Scan' in plan or 'Index Scan' in plan or 'Bitmap Heap Scan' in plan

    @pytest.mark.asyncio
    async def test_query_timeout(self, db_session):
        # Timeout de 1ms para forçar erro em query longa
        try:
            await db_session.execute(text("SET statement_timeout = 1"))
            await db_session.execute(text("SELECT pg_sleep(0.01)"))
            assert False, "Query deveria ter sido interrompida por timeout"
        except Exception as e:
            assert 'canceling statement due to statement timeout' in str(e) or 'timeout' in str(e).lower()
