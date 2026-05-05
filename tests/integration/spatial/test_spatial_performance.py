"""
Testes de performance para queries espaciais (RNF01 — resposta em até 2 segundos)
Marcador: @pytest.mark.performance — executados separadamente dos testes funcionais.

Estratégia:
- Warn (log): tempo > 1500ms
- Fail (hard): tempo > 3000ms (margem para variabilidade de CI/CD)
- Dados gerados via SQL direto com generate_series() para carregamento rápido
"""
import pytest
import time
import warnings
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


PERF_WARN_MS = 1500
PERF_FAIL_MS = 3000
SP_BOUNDS = (-47.0, -24.0, -45.0, -22.0)


def _validate_performance(operation: str, elapsed_ms: float):
    """Valida tempo de resposta: loga alerta e falha se ultrapassar threshold."""
    if elapsed_ms > PERF_WARN_MS:
        warnings.warn(
            f"[PERF WARN] {operation}: {elapsed_ms:.0f}ms excedeu limiar preventivo de {PERF_WARN_MS}ms"
        )
    assert elapsed_ms < PERF_FAIL_MS, (
        f"[PERF FAIL] {operation}: {elapsed_ms:.0f}ms excedeu limite rígido de {PERF_FAIL_MS}ms (RNF01)"
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.st_intersects
async def test_st_intersects_performance(session: AsyncSession):
    """
    Teste de performance para ST_Intersects com 2.000 imóveis rurais.
    Gera 2.000 imóveis com geometrias aleatórias na região SP e executa
    uma query ST_Intersects com um polígono de cobertura ampla.
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.commit()

    # 2. Gera 2.000 imóveis com SQL direto
    await session.execute(text(f"""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        SELECT
            'Perf Imovel ' || i,
            50 + (random() * 200),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.001
            ),
            ST_SetSRID(
                ST_Point(
                    {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                    {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                ),
                4326
            ),
            '{{"tipo": "rural"}}'::jsonb
        FROM generate_series(1, 2000) AS i
    """))
    await session.commit()

    # 3. Executa ST_Intersects e mede tempo
    query_polygon = text("""
        SELECT COUNT(*) AS total FROM imovel_rural
        WHERE ST_Intersects(
            geom,
            ST_SetSRID(
                ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326),
                4326
            )
        )
    """)

    start = time.perf_counter()
    result = await session.execute(query_polygon, {
        "xmin": -46.8, "ymin": -23.8, "xmax": -46.2, "ymax": -23.2
    })
    count = result.scalar()
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 4. Validações
    assert count > 0, "Query deveria retornar resultados"
    _validate_performance(f"ST_Intersects (2000 imoveis, envelope SP)", elapsed_ms)

    # 5. Limpa dados
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.st_distance
async def test_buffer_distance_performance(session: AsyncSession):
    """
    Teste de performance para ST_DWithin (distância) entre 2.000 imóveis e 1.000 alertas.
    Simula a query do endpoint /analytics/desmatamento/buffer-imoveis.
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'PERF_%'"))
    await session.commit()

    # 2. Gera 2.000 imóveis
    await session.execute(text(f"""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        SELECT
            'Perf Imovel ' || i,
            50 + (random() * 200),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.001
            ),
            ST_SetSRID(
                ST_Point(
                    {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                    {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                ),
                4326
            ),
            '{{"tipo": "rural"}}'::jsonb
        FROM generate_series(1, 2000) AS i
    """))

    # Gera 1.000 alertas de desmatamento
    await session.execute(text(f"""
        INSERT INTO desmatamento_alerta (id_origem, tipo_alerta, area_ha, geom)
        SELECT
            'PERF_ALERTA_' || i,
            'desmatamento',
            5 + (random() * 50),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.0005
            )
        FROM generate_series(1, 1000) AS i
    """))
    await session.commit()

    # 3. Executa query de buffer/distância (ST_DWithin + ST_Distance) e mede tempo
    query_buffer = text("""
        SELECT
            i.id::text,
            i.nome_imovel,
            a.id::text AS alerta_id,
            ROUND(ST_Distance(i.geom::geography, a.geom::geography)::numeric, 2)::float AS distancia_m
        FROM imovel_rural i
        JOIN desmatamento_alerta a
            ON ST_DWithin(i.geom::geography, a.geom::geography, 5000)
        ORDER BY distancia_m
        LIMIT 100
    """)

    start = time.perf_counter()
    result = await session.execute(query_buffer)
    rows = result.fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 4. Validações
    _validate_performance(
        f"ST_DWithin (2000 imoveis x 1000 alertas, raio 5km)",
        elapsed_ms
    )

    # 5. Limpa dados
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.execute(text("DELETE FROM desmatamento_alerta WHERE id_origem LIKE 'PERF_%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
async def test_endpoint_sobreposicoes_performance(client: TestClient, session: AsyncSession):
    """
    Teste de performance para GET /analytics/sobreposicoes/areas com 1.000 relações de sobreposição.
    Gera imóveis, UCs e relacionamentos via SQL direto, depois mede tempo de resposta do endpoint.
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Perf UC%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.commit()

    # 2. Gera 2.000 imóveis
    await session.execute(text(f"""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        SELECT
            'Perf Imovel ' || i,
            50 + (random() * 200),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.001
            ),
            ST_SetSRID(
                ST_Point(
                    {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                    {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                ),
                4326
            ),
            '{{"tipo": "rural"}}'::jsonb
        FROM generate_series(1, 2000) AS i
    """))

    # Gera 20 UCs
    await session.execute(text(f"""
        INSERT INTO unidade_conservacao (nome, categoria, esfera, grupo_snuc, area_ha, geom, id_origem)
        SELECT
            'Perf UC ' || i,
            'Parque',
            'Federal',
            'Protecao Integral',
            100 + (random() * 900),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.005
            ),
            'PERF-UC-' || i
        FROM generate_series(1, 20) AS i
    """))
    await session.commit()

    # Gera 1.000 relacionamentos (imovel <-> UC)
    await session.execute(text("""
        INSERT INTO rel_imovel_uc (imovel_rural_id, unidade_conservacao_id, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
        SELECT
            i.id,
            u.id,
            10 + (random() * 90),
            ROUND((10 + (random() * 90))::numeric, 2)::float,
            (ARRAY['parcial', 'total', 'marginal'])[1 + floor(random() * 3)::int]
        FROM (SELECT id FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%' ORDER BY random() LIMIT 1000) i
        CROSS JOIN LATERAL (
            SELECT id FROM unidade_conservacao WHERE nome LIKE 'Perf UC%' ORDER BY random() LIMIT 1
        ) u
    """))
    await session.commit()

    # 3. Mede tempo de resposta do endpoint HTTP
    start = time.perf_counter()
    response = client.get("/analytics/sobreposicoes/areas?tipo_area=uc&limite=100")
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] > 0
    _validate_performance(
        f"GET /analytics/sobreposicoes/areas (1000 relacoes, tipo=uc)",
        elapsed_ms
    )

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Perf UC%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf Imovel%'"))
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
async def test_endpoint_resumo_performance(client: TestClient, session: AsyncSession):
    """
    Teste de performance para GET /analytics/sobreposicoes/resumo com 2.000 relações
    distribuídas entre UC, TI, quilombola e assentamento.
    """
    # 1. Limpa dados anteriores
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf R Imovel%'"))
    await session.commit()

    # 2. Gera 2.000 imóveis
    await session.execute(text(f"""
        INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
        SELECT
            'Perf R Imovel ' || i,
            50 + (random() * 200),
            ST_Buffer(
                ST_SetSRID(
                    ST_Point(
                        {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                        {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                    ),
                    4326
                ),
                0.001
            ),
            ST_SetSRID(
                ST_Point(
                    {SP_BOUNDS[0]} + (random() * ({SP_BOUNDS[2]} - {SP_BOUNDS[0]})),
                    {SP_BOUNDS[1]} + (random() * ({SP_BOUNDS[3]} - {SP_BOUNDS[1]}))
                ),
                4326
            ),
            '{{"tipo": "rural"}}'::jsonb
        FROM generate_series(1, 2000) AS i
    """))

    # Gera 10 áreas de cada tipo
    await session.execute(text(f"""
        INSERT INTO unidade_conservacao (nome, categoria, esfera, grupo_snuc, area_ha, geom, id_origem)
        SELECT 'Perf R UC ' || i, 'Parque', 'Federal', 'Protecao Integral', 500,
               ST_Buffer(ST_SetSRID(ST_Point({SP_BOUNDS[0]} + random() * 2, {SP_BOUNDS[1]} + random() * 2), 4326), 0.005),
               'PERF-R-UC-' || i
        FROM generate_series(1, 10) AS i
    """))
    await session.execute(text(f"""
        INSERT INTO terra_indigena (nome, fase, area_ha, geom, id_origem)
        SELECT 'Perf R TI ' || i, 'Homologada', 800,
               ST_Buffer(ST_SetSRID(ST_Point({SP_BOUNDS[0]} + random() * 2, {SP_BOUNDS[1]} + random() * 2), 4326), 0.005),
               'PERF-R-TI-' || i
        FROM generate_series(1, 10) AS i
    """))
    await session.execute(text(f"""
        INSERT INTO territorio_quilombola (nome, area_ha, geom, id_origem)
        SELECT 'Perf R TQ ' || i, 300,
               ST_Buffer(ST_SetSRID(ST_Point({SP_BOUNDS[0]} + random() * 2, {SP_BOUNDS[1]} + random() * 2), 4326), 0.005),
               'PERF-R-TQ-' || i
        FROM generate_series(1, 10) AS i
    """))
    await session.execute(text(f"""
        INSERT INTO assentamento_rural (nome, modalidade, familias, area_ha, geom, id_origem)
        SELECT 'Perf R AR ' || i, 'PA', 50, 400,
               ST_Buffer(ST_SetSRID(ST_Point({SP_BOUNDS[0]} + random() * 2, {SP_BOUNDS[1]} + random() * 2), 4326), 0.005),
               'PERF-R-AR-' || i
        FROM generate_series(1, 10) AS i
    """))
    await session.commit()

    # Gera 500 relacionamentos por tipo (2.000 total)
    for table, area_table, area_col, prefix in [
        ("rel_imovel_uc", "unidade_conservacao", "id", "UC"),
        ("rel_imovel_ti", "terra_indigena", "id", "TI"),
        ("rel_imovel_quilombo", "territorio_quilombola", "id", "TQ"),
        ("rel_imovel_assentamento", "assentamento_rural", "id", "AR"),
    ]:
        await session.execute(text(f"""
            INSERT INTO {table} (imovel_rural_id, {area_col}, area_intersecao_ha, percentual_sobreposicao, tipo_relacao)
            SELECT
                i.id,
                a.id,
                10 + (random() * 90),
                ROUND((10 + (random() * 90))::numeric, 2)::float,
                (ARRAY['parcial', 'total', 'marginal'])[1 + floor(random() * 3)::int]
            FROM (SELECT id FROM imovel_rural WHERE nome_imovel LIKE 'Perf R Imovel%' ORDER BY random() LIMIT 500) i
            CROSS JOIN LATERAL (
                SELECT id FROM {area_table} WHERE nome LIKE 'Perf R {prefix}%' ORDER BY random() LIMIT 1
            ) a
        """))
    await session.commit()

    # 3. Mede tempo de resposta do endpoint HTTP
    start = time.perf_counter()
    response = client.get("/analytics/sobreposicoes/resumo")
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 4. Validações
    assert response.status_code == 200
    data = response.json()
    resumo = data["data"]
    assert resumo["imoveis_com_sobreposicao_uc"] > 0
    assert resumo["imoveis_com_sobreposicao_ti"] > 0
    assert resumo["imoveis_com_sobreposicao_quilombola"] > 0
    assert resumo["imoveis_com_sobreposicao_assentamento"] > 0
    _validate_performance(
        f"GET /analytics/sobreposicoes/resumo (2000 relacoes, 4 tipos)",
        elapsed_ms
    )

    # 5. Limpa dados
    await session.execute(text("DELETE FROM rel_imovel_uc"))
    await session.execute(text("DELETE FROM rel_imovel_ti"))
    await session.execute(text("DELETE FROM rel_imovel_quilombo"))
    await session.execute(text("DELETE FROM rel_imovel_assentamento"))
    await session.execute(text("DELETE FROM unidade_conservacao WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM terra_indigena WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM territorio_quilombola WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM assentamento_rural WHERE nome LIKE 'Perf R%'"))
    await session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Perf R Imovel%'"))
    await session.commit()
