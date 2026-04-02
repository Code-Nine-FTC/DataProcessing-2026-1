"""
ETL: Territórios Quilombolas — Fundação Cultural Palmares / INCRA
Fonte:  Acervo Fundiário do INCRA (WFS) — camada de territórios quilombolas
        https://acervofundiario.incra.gov.br/i3geo/ogc.php
Tabela: territorio_quilombola
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

WFS_URL = "https://acervofundiario.incra.gov.br/i3geo/ogc.php"
LAYER = "quilombola_titulado"

FONTE = {
    "nome": "Fundação Cultural Palmares - Territórios Quilombolas",
    "orgao_responsavel": "Fundação Cultural Palmares / INCRA",
    "url_origem": WFS_URL,
    "formato": "WFS/GeoJSON",
    "periodicidade": "irregular",
    "escopo_geografico": "nacional",
    "licenca": "Dados Abertos Gov",
}

DATASET = {
    "nome": "QUILOMBOLA_PALMARES",
    "descricao": "Territórios Quilombolas do Brasil - Acervo Fundiário INCRA/FCP",
    "versao": str(date.today().year),
    "data_referencia": date.today(),
}

_NOME = ("NOME_COMU", "nome_comunidade", "NOME", "nome", "NM_COMUNI")
_STATUS = ("STATUS", "status_processo", "FASE", "fase", "SIT_FUNDO")
_AREA = ("AREA_HA", "area_ha", "AREA_HECTA", "area")
_ID_ORIG = ("NR_PROCES", "nr_processo", "gid", "FID", "id")


def run():
    print("[palmares] Iniciando ETL...")
    engine = get_engine()

    print("[palmares] Baixando dados do WFS...")
    gdf = fetch_wfs(WFS_URL, LAYER, wfs_version="1.1.0")
    if gdf.empty:
        print("[palmares] Nenhum dado retornado pelo WFS.")
        return

    gdf = gdf.to_crs(epsg=4326)
    print(f"[palmares] {len(gdf)} registros recebidos. Preparando inserção...")

    rows = []
    for _, row in gdf.iterrows():
        geom = ensure_multipolygon(row.geometry)
        rows.append({
            "id": str(uuid.uuid4()),
            "id_origem": str(pick(row, _ID_ORIG, row.name)),
            "dataset_id": None,  # preenchido após criar dataset
            "nome": pick(row, _NOME),
            "status_processo": pick(row, _STATUS),
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
                INSERT INTO territorio_quilombola
                    (id, id_origem, dataset_id, nome, status_processo,
                     area_ha, geom, atributos_json)
                VALUES
                    (:id, :id_origem, :dataset_id, :nome, :status_processo,
                     :area_ha,
                     ST_GeomFromText(:geom_wkt, 4326),
                     CAST(:atributos_json AS JSONB))
            """),
            rows,
        )

    print(f"[palmares] {len(rows)} registros inseridos.")


if __name__ == "__main__":
    run()
