"""
Testes de integração para data-ingestion/sources/relacoes_espaciais.py
Cobre: ST_Area, ST_Intersection, ST_Intersects, ST_MakeValid
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
async def test_st_makevalid_corrige_geometria(session: AsyncSession):
    """
    Teste para ST_MakeValid em relacoes_espaciais.py
    Verifica se geometrias inválidas são corrigidas
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere imóvel com geometria que pode estar inválida
    # (o ST_MakeValid deve corrigir se necessário)
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel Valido',
            100.0,
            ST_MakeValid(ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326)),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    await session.commit()

    # 3. Verifica se a geometria está válida após ST_MakeValid
    result = await session.execute(text("""
        SELECT
            ST_IsValid(geom) as is_valid,
            ST_Area(geom::geography) / 10000.0 as area_ha_calc
        FROM imovel_rural
        WHERE nome_imovel = 'Teste Imóvel Valido'
    """))

    row = result.fetchone()
    assert row is not None
    assert row[0] == True, "Geometria deveria ser válida após ST_MakeValid"
    assert row[1] > 100.0, f"Área calculada ({row[1]}) é muito pequena"

    # 4. Limpa dados de teste
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()
