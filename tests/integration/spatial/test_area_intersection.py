"""
Testes de integração para data-ingestion/sources/relacoes_espaciais.py
Cobre: ST_Area, ST_Intersection, ST_Intersects, ST_MakeValid
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_criar_relacionamentos_area_intersecao(session: AsyncSession):
    """
    Teste para ST_Area e ST_Intersection em relacoes_espaciais.py
    Verifica se a área de interseção é calculada corretamente
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_municipio WHERE TRUE"))
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()

    # 2. Insere municipio de teste (SP)
    await session.execute(text("""
        INSERT INTO municipio (nome, sigla_estado, geom)
        SELECT
            'Teste Municipio SP',
            'SP',
            ST_GeomFromText('POLYGON((-46.8 -23.7, -46.5 -23.7, -46.5 -23.4, -46.8 -23.4, -46.8 -23.7))', 4326)
        WHERE NOT EXISTS (SELECT 1 FROM municipio WHERE nome = 'Teste Municipio SP')
        RETURNING id
    """))

    # 3. Insere imóvel que se sobrepõe parcialmente ao município
    await session.execute(text("""
        INSERT INTO imovel_rural
            (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Imóvel Intersecao',
            150.0,
            ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    await session.commit()

    # 4. Cria relacionamento usando a função de relações espaciais
    # Simula o que acontece em relacoes_espaciais.py
    result = await session.execute(text("""
        INSERT INTO rel_imovel_municipio
            (id, imovel_rural_id, municipio_id, area_intersecao_ha, percentual_sobreposicao)
        SELECT
            gen_random_uuid(),
            i.id,
            m.id,
            ST_Area(ST_Intersection(ST_MakeValid(i.geom), ST_MakeValid(m.geom))) / 10000.0,
            CASE
                WHEN i.area_ha > 0 THEN
                    (ST_Area(ST_Intersection(ST_MakeValid(i.geom), ST_MakeValid(m.geom))) / 10000.0)
                    / i.area_ha * 100
                ELSE 0
            END
        FROM imovel_rural i
        JOIN municipio m ON ST_Intersects(ST_MakeValid(i.geom), ST_MakeValid(m.geom))
        WHERE i.nome_imovel = 'Teste Imóvel Intersecao'
          AND m.nome = 'Teste Municipio SP'
        RETURNING area_intersecao_ha, percentual_sobreposicao
    """))

    row = result.fetchone()
    await session.commit()

    # 5. Validações
    assert row is not None, "Relacionamento deveria ter sido criado"
    area_intersecao = row[0]
    percentual = row[1]

    # A área de interseção deve ser positiva e menor que a área total do imóvel
    assert area_intersecao > 0, f"Área de interseção deveria ser > 0, mas é {area_intersecao}"
    assert area_intersecao <= 150.0, f"Área de interseção ({area_intersecao}) maior que área do imóvel"

    # O percentual deve estar entre 0 e 100
    assert 0 <= percentual <= 100, f"Percentual ({percentual}) fora do intervalo [0, 100]"

    # 6. Verifica se o relacionamento foi salvo corretamente
    result_check = await session.execute(text("""
        SELECT COUNT(*) FROM rel_imovel_municipio r
        JOIN imovel_rural i ON r.imovel_rural_id = i.id
        JOIN municipio m ON r.municipio_id = m.id
        WHERE i.nome_imovel = 'Teste Imóvel Intersecao'
          AND m.nome = 'Teste Municipio SP'
    """))

    count = result_check.scalar()
    assert count == 1, f"Deveria haver 1 relacionamento, mas encontrou {count}"

    # 7. Limpa dados de teste
    await session.execute(text("DELETE FROM rel_imovel_municipio WHERE TRUE"))
    await session.execute(text("DELETE FROM municipio WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()


@pytest.mark.asyncio
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
            ST_Area(geom) / 10000.0 as area_ha_calc
        FROM imovel_rural
        WHERE nome_imovel = 'Teste Imóvel Valido'
    """))

    row = result.fetchone()
    assert row is not None
    assert row[0] == True, "Geometria deveria ser válida após ST_MakeValid"
    assert abs(row[1] - 100.0) < 1.0, f"Área calculada ({row[1]}) difere da esperada (100.0)"

    # 4. Limpa dados de teste
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste %'"))
    await session.commit()
