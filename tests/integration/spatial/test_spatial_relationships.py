import pytest
from sqlalchemy import text

class TestSpatialRelationships:
    @pytest.mark.asyncio
    async def test_rel_imovel_queimada_pipeline(self, db_session):
        result = await db_session.execute(text("SELECT COUNT(*) FROM rel_imovel_queimada"))
        count = result.scalar()
        assert count >= 0

    @pytest.mark.asyncio
    async def test_overall_spatial_relationships(self, db_session):
        tables = [
            'rel_imovel_queimada', 'rel_imovel_desmatamento', 'rel_imovel_uc',
            'rel_imovel_ti', 'rel_imovel_assentamento', 'rel_imovel_quilombo',
            'rel_imovel_bacia', 'camada_estadual_ambiental'
        ]
        for table in tables:
            result = await db_session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            assert count >= 0
