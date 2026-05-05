"""
Testes de integração para endpoint GET /analytics/sobreposicoes/resumo
Cobre: resumo de sobreposições por tipo de área especial (RF04 - sobreposição)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_resumo_sobreposicoes_com_dados(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/resumo
    Valida que o resumo retorna contagens corretas de imóveis com sobreposição
    por tipo de área especial (UC, TI, quilombola, assentamento)
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Resumo%'"))
    await session.commit()

    # 2. Insere 4 imóveis
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES
            ('Teste Resumo UC', 100.0,
             ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
             ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
             '{"tipo": "rural"}'::jsonb),
            ('Teste Resumo TI', 120.0,
             ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
             ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
             '{"tipo": "rural"}'::jsonb),
            ('Teste Resumo Quilombo', 80.0,
             ST_GeomFromText('POLYGON((-46.80 -23.70, -46.70 -23.70, -46.70 -23.60, -46.80 -23.60, -46.80 -23.70))', 4326),
             ST_GeomFromText('POINT(-46.75 -23.65)', 4326),
             '{"tipo": "rural"}'::jsonb),
            ('Teste Resumo Assentamento', 60.0,
             ST_GeomFromText('POLYGON((-46.75 -23.65, -46.65 -23.65, -46.65 -23.55, -46.75 -23.55, -46.75 -23.65))', 4326),
             ST_GeomFromText('POINT(-46.70 -23.60)', 4326),
             '{"tipo": "rural"}'::jsonb)
    """))

    imovel_uc_id = (await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Resumo UC'"))).scalar()
    imovel_ti_id = (await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Resumo TI'"))).scalar()
    imovel_quilombo_id = (await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Resumo Quilombo'"))).scalar()
    imovel_assentamento_id = (await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Resumo Assentamento'"))).scalar()

    # Insere áreas especiais
    await session.execute(text("""
        INSERT INTO unidade_conservacao (nome, categoria, esfera, grupo_snuc, area_ha, geom, id_origem)
        VALUES ('UC Teste Resumo', 'Parque', 'Federal', 'Proteção Integral', 500.0,
                ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
                'UC-RESUMO-01')
    """))
    uc_id = (await session.execute(text("SELECT id FROM unidade_conservacao WHERE nome = 'UC Teste Resumo'"))).scalar()

    await session.execute(text("""
        INSERT INTO terra_indigena (nome, fase, area_ha, geom, id_origem)
        VALUES ('TI Teste Resumo', 'Homologada', 800.0,
                ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
                'TI-RESUMO-01')
    """))
    ti_id = (await session.execute(text("SELECT id FROM terra_indigena WHERE nome = 'TI Teste Resumo'"))).scalar()

    await session.execute(text("""
        INSERT INTO territorio_quilombola (nome, area_ha, geom, id_origem)
        VALUES ('TQ Teste Resumo', 300.0,
                ST_GeomFromText('POLYGON((-46.80 -23.70, -46.70 -23.70, -46.70 -23.60, -46.80 -23.60, -46.80 -23.70))', 4326),
                'TQ-RESUMO-01')
    """))
    tq_id = (await session.execute(text("SELECT id FROM territorio_quilombola WHERE nome = 'TQ Teste Resumo'"))).scalar()

    await session.execute(text("""
        INSERT INTO assentamento_rural (nome, modalidade, familias, area_ha, geom, id_origem)
        VALUES ('AR Teste Resumo', 'PA', 50, 400.0,
                ST_GeomFromText('POLYGON((-46.75 -23.65, -46.65 -23.65, -46.65 -23.55, -46.75 -23.55, -46.75 -23.65))', 4326),
                'AR-RESUMO-01')
    """))
    ar_id = (await session.execute(text("SELECT id FROM assentamento_rural WHERE nome = 'AR Teste Resumo'"))).scalar()

    # Insere relacionamentos (1 por tipo)
    await session.execute(text(f"""
        INSERT INTO rel_imovel_uc (imovel_rural_id, unidade_conservacao_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_uc_id}', '{uc_id}', 50.0, 50.0, 'parcial')
    """))
    await session.execute(text(f"""
        INSERT INTO rel_imovel_ti (imovel_rural_id, terra_indigena_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_ti_id}', '{ti_id}', 30.0, 25.0, 'parcial')
    """))
    await session.execute(text(f"""
        INSERT INTO rel_imovel_quilombo (imovel_rural_id, territorio_quilombola_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_quilombo_id}', '{tq_id}', 45.0, 50.0, 'parcial')
    """))
    await session.execute(text(f"""
        INSERT INTO rel_imovel_assentamento (imovel_rural_id, assentamento_rural_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_assentamento_id}', '{ar_id}', 60.0, 100.0, 'total')
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/resumo")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    resumo = data["data"]

    assert resumo["imoveis_com_sobreposicao_uc"] == 1
    assert resumo["imoveis_com_sobreposicao_ti"] == 1
    assert resumo["imoveis_com_sobreposicao_quilombola"] == 1
    assert resumo["imoveis_com_sobreposicao_assentamento"] == 1
    assert resumo["total_imoveis"] > 0

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste Resumo%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Resumo%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_resumo_sobreposicoes_vazio(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/resumo
    Valida que o resumo retorna zeros quando não há sobreposições
    """
    # 1. Limpa todas as relações de sobreposição
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.commit()

    # 2. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/resumo")

    # 3. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    resumo = data["data"]

    assert resumo["imoveis_com_sobreposicao_uc"] == 0
    assert resumo["imoveis_com_sobreposicao_ti"] == 0
    assert resumo["imoveis_com_sobreposicao_quilombola"] == 0
    assert resumo["imoveis_com_sobreposicao_assentamento"] == 0
    assert "total_imoveis" in resumo
