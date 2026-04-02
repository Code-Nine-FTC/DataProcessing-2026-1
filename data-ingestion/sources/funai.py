"""
ETL: Terras Indígenas — FUNAI
Fonte:  GeoServer da FUNAI (https://geoserver.funai.gov.br/geoserver/Funai/ows)
Tabela: terra_indigena
"""
import sys
import uuid
from datetime import date

from sqlalchemy import text

sys.path.insert(0, ".")
sys.path.insert(0, "data-ingestion")
from models.database import get_engine
from loader import get_or_create_fonte_dado, get_or_create_dataset
from utils import fetch_wfs, ensure_multipolygon, safe_float, row_to_json, pick

WFS_URL = "https://geoserver.funai.gov.br/geoserver/Funai/ows"
LAYER = "Funai:tis_poligonais"

FONTE = {
    "nome": "FUNAI - Terras Indígenas",
    "orgao_responsavel": "Fundação Nacional dos Povos Indígenas",
    "url_origem": WFS_URL,
    "formato": "WFS/GeoJSON",
    "periodicidade": "irregular",
    "escopo_geografico": "nacional",
    "licenca": "Dados Abertos Gov",
}

DATASET = {
    "nome": f"TI_FUNAI_{date.today().isoformat()}",
    "descricao": "Terras Indígenas do Brasil - GeoServer FUNAI",
    "versao": str(date.today().year),
    "data_referencia": date.today(),
}

_NOME = ("terranome", "TERRANOME", "nome_ti", "nome")
_FASE = ("fase_ti", "FASE_TI", "fase", "situacao")
_AREA = ("areaoficia", "AREAOFICIA", "area_ha", "area")
_ID_ORIG = ("gid", "FID", "cod_ti", "id")


def run():
    print("[funai] Iniciando ETL...")
    engine = get_engine()

    print("[funai] Baixando dados do WFS...")
    gdf = fetch_wfs(WFS_URL, LAYER)
    if gdf.empty:
        print("[funai] Nenhum dado retornado pelo WFS.")
        return

    gdf = gdf.to_crs(epsg=4326)
    print(f"[funai] {len(gdf)} registros recebidos. Preparando inserção...")

    rows = []
    for _, row in gdf.iterrows():
        geom = ensure_multipolygon(row.geometry)
        rows.append({
            "id": str(uuid.uuid4()),
            "id_origem": str(pick(row, _ID_ORIG, row.name)),
            "dataset_id": None,  # preenchido após criar dataset
            "nome": pick(row, _NOME),
            "fase": pick(row, _FASE),
            "area_ha": safe_float(pick(row, _AREA)),
            "geom_wkt": geom.wkt if geom else None,
            "atributos_json": row_to_json(row),
        })

    # Tudo numa única transação — se o INSERT falhar, dataset não é commitado
    with engine.begin() as conn:
        fonte_id = get_or_create_fonte_dado(conn, **FONTE)
        dataset_id, is_new = get_or_create_dataset(conn, fonte_id, **DATASET)

        if not is_new:
            return

        for r in rows:
            r["dataset_id"] = dataset_id

        conn.execute(
            text("""
                INSERT INTO terra_indigena
                    (id, id_origem, dataset_id, nome, fase, area_ha, geom, atributos_json)
                VALUES
                    (:id, :id_origem, :dataset_id, :nome, :fase, :area_ha,
                     ST_GeomFromText(:geom_wkt, 4326),
                     CAST(:atributos_json AS JSONB))
            """),
            rows,
        )

    print(f"[funai] {len(rows)} registros inseridos.")


if __name__ == "__main__":
    run()
