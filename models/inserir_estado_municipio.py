# inserir_estado_municipio.py

import requests
from shapely.geometry import shape
from geoalchemy2.shape import from_shape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_model import Estado, Municipio

# ----------------------------------
# CONFIG
# ----------------------------------
DATABASE_URL = "postgresql+psycopg2://visiona:visiona@localhost:5432/visiona"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

ESTADO_ID_IBGE = 35  # São Paulo


# ----------------------------------
# EXTRACT
# ----------------------------------

def get_malha_municipios(estado_id: int):
    url = f"https://servicodados.ibge.gov.br/api/v4/malhas/estados/{estado_id}?formato=application/vnd.geo+json&resolucao=2&intrarregiao=municipio"
    print("[Extract] Baixando geometria dos municípios...")
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    print(f"[Extract] Features recebidas: {len(geojson.get('features', []))}")

    return geojson


def get_municipios_info(estado_id: int):
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_id}/municipios"

    print("[Extract] Baixando nomes dos municípios...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    data = response.json()

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

def inserir_estado(session, sigla: str, nome: str, geom):
    print("[Load] Verificando estado...")

    estado = session.query(Estado).filter_by(sigla=sigla).first()

    if estado:
        print(f"[Load] Estado já existe: {sigla}")
        return estado.id

    print("[Load] Inserindo novo estado...")

    novo_estado = Estado(
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
        geojson = get_malha_municipios(ESTADO_ID_IBGE)
        mapa_info = get_municipios_info(ESTADO_ID_IBGE)

        # TRANSFORM
        municipios = transform(geojson, mapa_info)

        # pega geometria do estado (primeira feature)
        estado_geom = shape(geojson["features"][0]["geometry"])

        # LOAD
        estado_id = inserir_estado(
            session,
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