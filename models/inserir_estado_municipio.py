# inserir_estado_municipio.py

import os
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException
from shapely.geometry import shape, MultiPolygon
from geoalchemy2.shape import from_shape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from db_model import Estado, Municipio

# ----------------------------------
# CONFIG
# ----------------------------------
load_dotenv()

_raw_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://codenine:sabotagem@localhost:5433/visiona-dev")
# Garante driver síncrono (psycopg2), não asyncpg
DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

ESTADO_ID_IBGE = 35  # São Paulo


# ----------------------------------
# EXTRACT
# ----------------------------------

def _get_json(url: str, timeout: int = 120) -> dict:
    """Faz GET e retorna JSON com tratamento de erros de rede."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Timeout:
        raise RuntimeError(f"Timeout ao acessar: {url}")
    except ConnectionError:
        raise RuntimeError(f"Falha de conexão ao acessar: {url}")
    except RequestException as e:
        raise RuntimeError(f"Erro HTTP ao acessar {url}: {str(e)}")


def get_malha_estado(estado_id: int):
    url = f"https://servicodados.ibge.gov.br/api/v4/malhas/estados/{estado_id}?formato=application/vnd.geo+json"
    print("[Extract] Baixando geometria do estado...")
    return _get_json(url)


def get_malha_municipios(estado_id: int):
    url = f"https://servicodados.ibge.gov.br/api/v4/malhas/estados/{estado_id}?formato=application/vnd.geo+json&resolucao=2&intrarregiao=municipio"
    print("[Extract] Baixando geometria dos municípios...")
    geojson = _get_json(url)
    print(f"[Extract] Features recebidas: {len(geojson.get('features', []))}")

    return geojson


def get_municipios_info(estado_id: int):
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_id}/municipios"

    print("[Extract] Baixando nomes dos municípios...")
    data = _get_json(url, timeout=60)

    mapa = {}

    for m in data:
        codigo = str(m["id"])

        uf = (
            m.get("microrregiao", {})
             .get("mesorregiao", {})
             .get("UF", {})
             .get("sigla")
        )

        mapa[codigo] = {
            "nome": m["nome"],
            "uf": uf
        }

    return mapa


# ----------------------------------
# TRANSFORM
# ----------------------------------

def transform(geojson, mapa_info):
    print("[Transform] Processando dados...")

    municipios = []

    for feature in geojson["features"]:
        props = feature.get("properties", {})
        codarea = str(props.get("codarea"))

        info = mapa_info.get(codarea)

        if not info:
            print(f"⚠️ Sem info: {codarea}")
            continue

        geom = shape(feature["geometry"])

        # corrigir geometria inválida
        if not geom.is_valid:
            geom = geom.buffer(0)

        # garantir MultiPolygon
        if geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])

        municipios.append({
            "nome": info["nome"],
            "codigo_ibge": codarea,
            "sigla_uf": info["uf"],
            "geometry": geom
        })

    print(f"[Transform] Total municípios: {len(municipios)}")
    return municipios


# ----------------------------------
# LOAD
# ----------------------------------

def inserir_estado(session, id: int, sigla: str, nome: str, geom):
    print("[Load] Verificando estado...")

    estado = session.query(Estado).filter_by(sigla=sigla).first()

    if estado:
        print(f"[Load] Estado já existe: {sigla} (id={estado.id})")
        return estado.id

    print("[Load] Inserindo novo estado...")

    novo_estado = Estado(
        id=id,
        sigla=sigla,
        nome=nome,
        geom=from_shape(geom, srid=4326)
    )

    session.add(novo_estado)
    session.commit()

    return novo_estado.id


def inserir_municipios(session, municipios, estado_id):
    print("[Load] Inserindo municípios...")

    existentes = {
        m.codigo_ibge for m in session.query(Municipio.codigo_ibge).all()
    }

    novos = []

    for m in municipios:
        if m["codigo_ibge"] in existentes:
            continue

        obj = Municipio(
            nome=m["nome"],
            codigo_ibge=m["codigo_ibge"],
            estado_id=estado_id,
            geom=from_shape(m["geometry"], srid=4326)
        )
        novos.append(obj)

    session.bulk_save_objects(novos)
    session.commit()

    print(f"[Load] Inseridos: {len(novos)}")


# ----------------------------------
# PIPELINE
# ----------------------------------

def run():
    session = SessionLocal()

    try:
        # EXTRACT
        estado_geojson = get_malha_estado(ESTADO_ID_IBGE)
        geojson = get_malha_municipios(ESTADO_ID_IBGE)
        mapa_info = get_municipios_info(ESTADO_ID_IBGE)

        # TRANSFORM
        municipios = transform(geojson, mapa_info)

        # geometria do estado (endpoint dedicado)
        estado_geom = shape(estado_geojson["features"][0]["geometry"])
        if not estado_geom.is_valid:
            estado_geom = estado_geom.buffer(0)
        if estado_geom.geom_type == "Polygon":
            estado_geom = MultiPolygon([estado_geom])

        # LOAD
        estado_id = inserir_estado(
            session,
            id=ESTADO_ID_IBGE,
            sigla="SP",
            nome="São Paulo",
            geom=estado_geom
        )

        inserir_municipios(session, municipios, estado_id)

        print("✅ Pipeline finalizada!")

    finally:
        session.close()


# ----------------------------------
# MAIN
# ----------------------------------

if __name__ == "__main__":
    run()