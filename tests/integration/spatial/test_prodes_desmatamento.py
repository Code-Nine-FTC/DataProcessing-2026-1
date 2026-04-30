"""
Testes de integração para data-ingestion/sources/prodes_desmatamento.py
Cobre: ST_Intersects na vinculação de alertas a municípios
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from data_ingestion.sources.prodes_desmatamento import _link_desmatamento_to_municipios


@pytest.mark.asyncio
async def test_link_desmatamento_to_municipios(session: AsyncSession):
    """
    Teste para ST_Intersects em _link_desmatamento_to_municipios
    Verifica se alertas de desmatamento são vinculadas aos municípios corretos
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'TEST_%'"))
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere município de teste (SP)
    result = await session.execute(text("""
        INSERT INTO municipio (nome, sigla_estado, geom)
        SELECT
            'Teste Municipio Link',
            'SP',
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio Link')
        RETURNING id
    """))
    municipio_id = result.fetchone()[0]
    await session.commit()

    # 3. Insere alerta de desmatamento DENTRO do município
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (id, id_origem, dataset_id, data_ocorrencia, tipo_alerta, area_ha, municipio_id, geom, atributos_json)
        VALUES (
            gen_random_uuid(),
            'TEST_PRODES_001',
            NULL,
            CURRENT_DATE,
            'desmatamento',
            10.5,
            NULL,  -- Ainda não vinculado
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"fonte": "PRODES"}'::jsonb
        )
    """))

    # Alerta FORA do município (não deve ser vinculado)
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (id, id_origem, dataset_id, data_ocorrencia, tipo_alerta, area_ha, municipio_id, geom, atributos_json)
        VALUES (
            gen_random_uuid(),
            'TEST_PRODES_002',
            NULL,
            CURRENT_DATE,
            'desmatamento',
            5.0,
            NULL,  -- Ainda não vinculado
            ST_GeomFromText('POINT(-35.0 -20.0)', 4326),  -- Oceano
            '{"fonte": "PRODES"}'::jsonb
        )
    """))
    await session.commit()

    # 4. Executa a função de vinculação (usa ST_Intersects)
    # Precisa da engine síncrona (a função usa engine.begin())
    sync_engine = session.bind.sync_engine if hasattr(session.bind, 'sync_engine') else session.bind
    _link_desmatamento_to_municipios(sync_engine, dataset_id=None)

    # 5. Verifica se o alerta dentro do município foi vinculado
    result_check = await session.execute(text("""
        SELECT COUNT(*) FROM desmatamento_alerta da
        JOIN municipio m ON da.municipio_id = m.id
        WHERE da.id_origem = 'TEST_PRODES_001'
          AND m.nome = 'Teste Municipio Link'
    """))
    count_vinculado = result_check.scalar()
    assert count_vinculado == 1, f"Alerta deveria estar vinculado ao município, mas count={count_vinculado}"

    # 6. Verifica se o alerta fora NÃO foi vinculado
    result_check2 = await session.execute(text("""
        SELECT municipio_id FROM desmatamento_alerta
        WHERE id_origem = 'TEST_PRODES_002'
    """))
    municipio_id_alerta2 = result_check2.fetchone()[0]
    assert municipio_id_alerta2 is None, "Alerta fora do município não deveria estar vinculado"

    # 7. Limpeza
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'TEST_%'"))
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
async def test_link_desmatamento_with_dataset_filter(session: AsyncSession):
    """
    Teste para ST_Intersects com filtro de dataset_id
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'TEST_%'"))
    await session.execute(text("DELETE FROM dataset WHERE nome LIKE 'Teste %'"))
    await session.commit()

    # 2. Cria dataset de teste
    result = await session.execute(text("""
        INSERT INTO dataset (id, fonte_dado_id, nome, descricao)
        VALUES (
            gen_random_uuid(),
            (SELECT id FROM fonte_dado LIMIT 1),
            'Teste Dataset PRODES',
            'Dataset de teste'
        )
        RETURNING id
    """))
    dataset_id = result.fetchone()[0]
    await session.commit()

    # 3. Insere alerta com dataset_id específico
    await session.execute(text("""
        INSERT INTO desmatamento_alerta
            (id, id_origem, dataset_id, data_ocorrencia, tipo_alerta, area_ha, geom, atributos_json)
        VALUES (
            gen_random_uuid(),
            'TEST_PRODES_003',
            :ds_id,
            CURRENT_DATE,
            'desmatamento',
            8.0,
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"fonte": "PRODES"}'::jsonb
        )
    """), {"ds_id": dataset_id})

    # 4. Executa vinculação filtrando pelo dataset
    sync_engine = session.bind.sync_engine if hasattr(session.bind, 'sync_engine') else session.bind
    _link_desmatamento_to_municipios(sync_engine, dataset_id=str(dataset_id))

    # 5. Verifica se o alerta foi vinculado
    result_check = await session.execute(text("""
        SELECT municipio_id FROM desmatamento_alerta
        WHERE id_origem = 'TEST_PRODES_003'
    """))
    municipio_id_result = result_check.fetchone()[0]
    assert municipio_id_result is not None, "Alerta com dataset específico deveria ser vinculado"

    # 6. Limpeza
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'TEST_%'"))
    await session.execute(text("DELETE FROM dataset WHERE nome LIKE 'Teste %'"))
    await session.commit()
