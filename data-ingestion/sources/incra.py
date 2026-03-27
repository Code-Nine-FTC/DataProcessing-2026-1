"""
ETL: Assentamentos Rurais — INCRA
Fonte:  Acervo Fundiário do INCRA (WFS)
        https://acervofundiario.incra.gov.br/i3geo/ogc.php
Tabela: assentamento_rural
"""
import sys
import uuid
from datetime import date

from sqlalchemy import text

sys.path.insert(0, ".")
sys.path.insert(0, "data-ingestion")
from models.database import get_engine
from loader import get_or_create_fonte_dado, get_or_create_dataset
from utils import fetch_wfs, ensure_multipolygon, safe_float, safe_int, row_to_json, pick

WFS_URL = "https://acervofundiario.incra.gov.br/i3geo/ogc.php"
LAYER = "ass_legalizados"

FONTE = {
    "nome": "INCRA - Assentamentos Rurais",
    "orgao_responsavel": "Instituto Nacional de Colonização e Reforma Agrária",
    "url_origem": WFS_URL,
    "formato": "WFS/GeoJSON",
    "periodicidade": "irregular",
    "escopo_geografico": "nacional",
    "licenca": "Dados Abertos Gov",
}

DATASET = {
    "nome": f"ASSENTAMENTOS_INCRA_{date.today().isoformat()}",
    "descricao": "Assentamentos Rurais do Brasil - Acervo Fundiário INCRA",
    "versao": str(date.today().year),
    "data_referencia": date.today(),
}

_NOME = ("NOME_PROJE", "nome_projeto", "NOME", "nome")
_FAMILIAS = ("QTDE_FAMIL", "num_familias", "familias", "QT_FAMILIA")
_MODALIDADE = ("MODALI", "modalidade", "MODALIDADE", "mod")
_AREA = ("AREA_HECTA", "area_ha", "AREA_HA", "area")
_ID_ORIG = ("CD_SIPRA", "cod_sipra", "gid", "FID", "id")


def run():
    print("[incra] Iniciando ETL...")
    engine = get_engine()

    with engine.begin() as conn:
        fonte_id = get_or_create_fonte_dado(conn, **FONTE)
        dataset_id, is_new = get_or_create_dataset(conn, fonte_id, **DATASET)

    if not is_new:
        return

    print("[incra] Baixando dados do WFS...")
    gdf = fetch_wfs(WFS_URL, LAYER, wfs_version="1.1.0")
    if gdf.empty:
        print("[incra] Nenhum dado retornado pelo WFS.")
        return

    gdf = gdf.to_crs(epsg=4326)
    print(f"[incra] {len(gdf)} registros recebidos. Preparando inserção...")

    rows = []
    for _, row in gdf.iterrows():
        geom = ensure_multipolygon(row.geometry)
        rows.append({
            "id": str(uuid.uuid4()),
            "id_origem": str(pick(row, _ID_ORIG, row.name)),
            "dataset_id": dataset_id,
            "nome": pick(row, _NOME),
            "modalidade": pick(row, _MODALIDADE),
            "familias": safe_int(pick(row, _FAMILIAS)),
            "area_ha": safe_float(pick(row, _AREA)),
            "geom_wkt": geom.wkt if geom else None,
            "atributos_json": row_to_json(row),
        })

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO assentamento_rural
                    (id, id_origem, dataset_id, nome, modalidade, familias,
                     area_ha, geom, atributos_json)
                VALUES
                    (:id, :id_origem, :dataset_id, :nome, :modalidade, :familias,
                     :area_ha,
                     ST_GeomFromText(:geom_wkt, 4326),
                     CAST(:atributos_json AS JSONB))
            """),
            rows,
        )

    print(f"[incra] {len(rows)} registros inseridos.")


if __name__ == "__main__":
    run()
