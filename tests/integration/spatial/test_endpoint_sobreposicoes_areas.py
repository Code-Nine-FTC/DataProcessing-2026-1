"""
Testes de integração para endpoint GET /analytics/sobreposicoes/areas
Cobre: tipos uc, ti, quilombo, assentamento, todos (RF04 - sobreposição)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_uc(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas com tipo=uc
    Valida sobreposição de imóveis com unidades de conservação
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Sobreposicao UC',
            100.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    imovel_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao UC'"))
    imovel_id = imovel_result.scalar()

    # Insere UC
    await session.execute(text("""
        INSERT INTO unidade_conservacao (
            nome, categoria, esfera, grupo_snuc, area_ha, geom, id_origem
        )
        VALUES (
            'UC Teste Integração',
            'Parque',
            'Federal',
            'Proteção Integral',
            500.0,
            ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
            'UC-TESTE-01'
        )
    """))
    uc_result = await session.execute(text("SELECT id FROM unidade_conservacao WHERE nome = 'UC Teste Integração'"))
    uc_id = uc_result.scalar()

    # Insere relacionamento
    await session.execute(text(f"""
        INSERT INTO rel_imovel_uc (
            imovel_rural_id, unidade_conservacao_id,
            area_intersecao_ha, percentual_sobreposicao, tipo_relacao
        )
        VALUES (
            '{imovel_id}',
            '{uc_id}',
            50.0,
            50.0,
            'parcial'
        )
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=uc&limite=10")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data["data"]
    assert "itens" in data["data"]
    assert data["data"]["tipo_area"] == "uc"
    assert data["data"]["total"] > 0

    item = data["data"]["itens"][0]
    assert "imovel_id" in item
    assert "area_id" in item
    assert "area_intersecao_ha" in item
    assert item["tipo_relacao"] == "parcial"

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_ti(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas com tipo=ti
    Valida sobreposição de imóveis com terras indígenas
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao TI%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Sobreposicao TI',
            120.0,
            ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
            ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    imovel_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao TI'"))
    imovel_id = imovel_result.scalar()

    # Insere terra indígena
    await session.execute(text("""
        INSERT INTO terra_indigena (
            nome, fase, area_ha, geom, id_origem
        )
        VALUES (
            'TI Teste Integração',
            'Homologada',
            800.0,
            ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
            'TI-TESTE-01'
        )
    """))
    ti_result = await session.execute(text("SELECT id FROM terra_indigena WHERE nome = 'TI Teste Integração'"))
    ti_id = ti_result.scalar()

    # Insere relacionamento
    await session.execute(text(f"""
        INSERT INTO rel_imovel_ti (
            imovel_rural_id, terra_indigena_id,
            area_intersecao_ha, percentual_sobreposicao, tipo_relacao
        )
        VALUES (
            '{imovel_id}',
            '{ti_id}',
            30.0,
            25.0,
            'parcial'
        )
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=ti&limite=10")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["tipo_area"] == "ti"
    assert data["data"]["total"] > 0

    item = data["data"]["itens"][0]
    assert "imovel_id" in item
    assert "area_id" in item
    assert "area_intersecao_ha" in item
    assert item["percentual_sobreposicao"] == 25.0

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao TI%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_quilombo(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas com tipo=quilombo
    Valida sobreposição de imóveis com territórios quilombolas
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Quilombo%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Sobreposicao Quilombo',
            90.0,
            ST_GeomFromText('POLYGON((-46.80 -23.70, -46.70 -23.70, -46.70 -23.60, -46.80 -23.60, -46.80 -23.70))', 4326),
            ST_GeomFromText('POINT(-46.75 -23.65)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    imovel_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao Quilombo'"))
    imovel_id = imovel_result.scalar()

    # Insere território quilombola
    await session.execute(text("""
        INSERT INTO territorio_quilombola (
            nome, area_ha, geom, id_origem
        )
        VALUES (
            'TQ Teste Integração',
            300.0,
            ST_GeomFromText('POLYGON((-46.80 -23.70, -46.70 -23.70, -46.70 -23.60, -46.80 -23.60, -46.80 -23.70))', 4326),
            'TQ-TESTE-01'
        )
    """))
    tq_result = await session.execute(text("SELECT id FROM territorio_quilombola WHERE nome = 'TQ Teste Integração'"))
    tq_id = tq_result.scalar()

    # Insere relacionamento
    await session.execute(text(f"""
        INSERT INTO rel_imovel_quilombo (
            imovel_rural_id, territorio_quilombola_id,
            area_intersecao_ha, percentual_sobreposicao, tipo_relacao
        )
        VALUES (
            '{imovel_id}',
            '{tq_id}',
            45.0,
            50.0,
            'parcial'
        )
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=quilombo&limite=10")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["tipo_area"] == "quilombo"
    assert data["data"]["total"] > 0

    item = data["data"]["itens"][0]
    assert "imovel_id" in item
    assert "area_id" in item
    assert item["tipo_relacao"] == "parcial"

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Quilombo%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_assentamento(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas com tipo=assentamento
    Valida sobreposição de imóveis com assentamentos rurais
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Assentamento%'"))
    await session.commit()

    # 2. Insere imóvel
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES (
            'Teste Sobreposicao Assentamento',
            60.0,
            ST_GeomFromText('POLYGON((-46.75 -23.65, -46.65 -23.65, -46.65 -23.55, -46.75 -23.55, -46.75 -23.65))', 4326),
            ST_GeomFromText('POINT(-46.70 -23.60)', 4326),
            '{"tipo": "rural"}'::jsonb
        )
    """))
    imovel_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao Assentamento'"))
    imovel_id = imovel_result.scalar()

    # Insere assentamento rural
    await session.execute(text("""
        INSERT INTO assentamento_rural (
            nome, modalidade, familias, area_ha, geom, id_origem
        )
        VALUES (
            'AR Teste Integração',
            'PA',
            50,
            400.0,
            ST_GeomFromText('POLYGON((-46.75 -23.65, -46.65 -23.65, -46.65 -23.55, -46.75 -23.55, -46.75 -23.65))', 4326),
            'AR-TESTE-01'
        )
    """))
    ar_result = await session.execute(text("SELECT id FROM assentamento_rural WHERE nome = 'AR Teste Integração'"))
    ar_id = ar_result.scalar()

    # Insere relacionamento
    await session.execute(text(f"""
        INSERT INTO rel_imovel_assentamento (
            imovel_rural_id, assentamento_rural_id,
            area_intersecao_ha, percentual_sobreposicao, tipo_relacao
        )
        VALUES (
            '{imovel_id}',
            '{ar_id}',
            60.0,
            100.0,
            'total'
        )
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=assentamento&limite=10")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["tipo_area"] == "assentamento"
    assert data["data"]["total"] > 0

    item = data["data"]["itens"][0]
    assert "imovel_id" in item
    assert "area_id" in item
    assert item["percentual_sobreposicao"] == 100.0
    assert item["tipo_relacao"] == "total"

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Assentamento%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_todos(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas com tipo=todos
    Valida que o endpoint retorna sobreposições de todos os tipos combinados (UC + TI)
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Todos%'"))
    await session.commit()

    # 2. Insere 2 imóveis
    await session.execute(text("""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        VALUES
            ('Teste Sobreposicao Todos UC', 100.0,
             ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
             ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
             '{"tipo": "rural"}'::jsonb),
            ('Teste Sobreposicao Todos TI', 120.0,
             ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
             ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
             '{"tipo": "rural"}'::jsonb)
    """))

    imovel_uc_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao Todos UC'"))
    imovel_uc_id = imovel_uc_result.scalar()
    imovel_ti_result = await session.execute(text("SELECT id FROM imovel_rural WHERE nome_imovel = 'Teste Sobreposicao Todos TI'"))
    imovel_ti_id = imovel_ti_result.scalar()

    # Insere UC
    await session.execute(text("""
        INSERT INTO unidade_conservacao (
            nome, categoria, esfera, grupo_snuc, area_ha, geom, id_origem
        )
        VALUES ('UC Teste Todos', 'Parque', 'Federal', 'Proteção Integral', 500.0,
                ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
                'UC-TESTE-TODOS')
    """))
    uc_result = await session.execute(text("SELECT id FROM unidade_conservacao WHERE nome = 'UC Teste Todos'"))
    uc_id = uc_result.scalar()

    # Insere TI
    await session.execute(text("""
        INSERT INTO terra_indigena (
            nome, fase, area_ha, geom, id_origem
        )
        VALUES ('TI Teste Todos', 'Homologada', 800.0,
                ST_GeomFromText('POLYGON((-46.70 -23.60, -46.60 -23.60, -46.60 -23.50, -46.70 -23.50, -46.70 -23.60))', 4326),
                'TI-TESTE-TODOS')
    """))
    ti_result = await session.execute(text("SELECT id FROM terra_indigena WHERE nome = 'TI Teste Todos'"))
    ti_id = ti_result.scalar()

    # Insere relacionamentos
    await session.execute(text(f"""
        INSERT INTO rel_imovel_uc (imovel_rural_id, unidade_conservacao_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_uc_id}', '{uc_id}', 50.0, 50.0, 'parcial')
    """))
    await session.execute(text(f"""
        INSERT INTO rel_imovel_ti (imovel_rural_id, terra_indigena_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        VALUES ('{imovel_ti_id}', '{ti_id}', 30.0, 25.0, 'parcial')
    """))
    await session.commit()

    # 3. Testa endpoint HTTP
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=todos&limite=10")

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["tipo_area"] == "todos"
    assert data["data"]["total"] >= 2

    # Verifica que contém ambos os tipos
    tipos = {item["tipo_area"] for item in data["data"]["itens"]}
    assert "uc" in tipos
    assert "ti" in tipos

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Teste %'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Teste Sobreposicao Todos%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_endpoint_sobreposicoes_areas_vazio(client: TestClient, session: AsyncSession):
    """
    Teste de integração para endpoint GET /analytics/sobreposicoes/areas quando não há sobreposições
    Valida que o endpoint retorna total=0 e lista vazia
    """
    # 1. Limpa todas as relações de sobreposição
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.commit()

    # 2. Testa endpoint HTTP (sem dados)
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=uc&limite=10")

    # 3. Validações
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] == 0
    assert data["data"]["itens"] == []
    assert data["data"]["tipo_area"] == "uc"
