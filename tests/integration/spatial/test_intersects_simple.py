"""
Teste simplificado para prova de conceito da Fase 1
Executa via pytest síncrono para evitar problemas de event loop no Windows
"""
import pytest
import json
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv('.env.test')
load_dotenv()

# Configuração síncrona para teste simples
POSTGRES_USER = os.getenv("POSTGRES_USER", "test")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "test")
POSTGRES_DB = os.getenv("POSTGRES_DB", "test_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def test_st_intersects_query():
    """
    Teste síncrono simples para verificar se a query ST_Intersects funciona
    Prova de conceito da Fase 1
    """
    with SessionLocal() as session:
        # 1. Limpa dados anteriores
        session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Imóvel %'"))
        session.commit()

        # 2. Insere dados de teste (usando SQL direto para simplicidade)
        # Geometria 1: Polígono pequeno em SP
        session.execute(text("""
            INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
            VALUES ('Imóvel SP 1', 100.5,
                    ST_GeomFromText('POLYGON((-46.7 -23.6, -46.6 -23.6, -46.6 -23.5, -46.7 -23.5, -46.7 -23.6))', 4326),
                    ST_GeomFromText('POINT(-46.65 -23.55)', 4326),
                    '{"tipo": "rural", "cultura": "soja"}'::jsonb)
        """))

        # Geometria 2: Polígono menor em SP (dentro do primeiro)
        session.execute(text("""
            INSERT INTO imovel_rural (nome_imovel, area_ha, geom, centroid, atributos_json)
            VALUES ('Imóvel SP 2', 75.3,
                    ST_GeomFromText('POLYGON((-46.65 -23.55, -46.55 -23.55, -46.55 -23.45, -46.65 -23.45, -46.65 -23.55))', 4326),
                    ST_GeomFromText('POINT(-46.6 -23.5)', 4326),
                    '{"tipo": "rural", "cultura": "milho"}'::jsonb)
        """))
        session.commit()

        # 3. Teste 1: ST_Intersects com polígono que deve intersectar 2 imóveis
        sp_polygon = json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [-46.75, -23.65],
                [-46.55, -23.65],
                [-46.55, -23.45],
                [-46.75, -23.45],
                [-46.75, -23.65]
            ]]
        })

        result = session.execute(text("""
            SELECT id::text AS id, nome_imovel AS nome, area_ha,
                   ST_AsGeoJSON(geom)::json AS geom, atributos_json
            FROM imovel_rural
            WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
        """), {"geojson": sp_polygon}).fetchall()

        assert len(result) >= 2, f"Esperava pelo menos 2 imóveis, mas encontrou {len(result)}"
        nomes = [row.nome for row in result]
        assert "Imóvel SP 1" in nomes
        assert "Imóvel SP 2" in nomes

        # 4. Teste 2: Ponto que deve intersectar apenas 1 imóvel
        sp_ponto = json.dumps({"type": "Point", "coordinates": [-46.58, -23.48]})

        result_ponto = session.execute(text("""
            SELECT id::text AS id, nome_imovel AS nome, area_ha,
                   ST_AsGeoJSON(geom)::json AS geom, atributos_json
            FROM imovel_rural
            WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
        """), {"geojson": sp_ponto}).fetchall()

        assert len(result_ponto) == 1, f"Esperava exatamente 1 imóvel, mas encontrou {len(result_ponto)}"
        assert result_ponto[0].nome == "Imóvel SP 2"

        # 5. Teste 3: Geometria longe deve retornar vazio
        rj_polygon = json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [-43.2, -22.9],
                [-43.1, -22.9],
                [-43.1, -22.8],
                [-43.2, -22.8],
                [-43.2, -22.9]
            ]]
        })

        result_rj = session.execute(text("""
            SELECT id::text AS id, nome_imovel AS nome
            FROM imovel_rural
            WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
        """), {"geojson": rj_polygon}).fetchall()

        assert len(result_rj) == 0, f"Esperava 0 imóveis, mas encontrou {len(result_rj)}"

        # 6. Validações de estrutura
        for row in result:
            assert row.id is not None
            assert row.nome is not None
            assert row.area_ha > 0
            assert isinstance(row.geom, dict)
            assert isinstance(row.atributos_json, dict)

        print("✓ Teste de integração ST_Intersects passou!")

        # Limpa dados de teste
        session.execute(text("DELETE FROM imovel_rural WHERE nome_imovel LIKE 'Imóvel %'"))
        session.commit()
