"""
ETL: Camadas ambientais estaduais — DataGeo SP
Fonte:  GeoServer DataGeo (https://datageo.ambiente.sp.gov.br/geoserver/datageo/ows)
Tabela: camada_estadual_ambiental

Este conector baixa camadas estaduais prioritárias (ex.: UCs) e normaliza
para o mesmo formato usado pelo restante do pipeline.
"""
import os
import sys
import uuid
from datetime import date

from sqlalchemy import text

sys.path.insert(0, ".")
sys.path.insert(0, "data-ingestion")

from models.config.connection import get_engine  # noqa: E402
from loader import get_or_create_dataset, get_or_create_fonte_dado  # noqa: E402
from utils import ensure_multipolygon, fetch_wfs, pick, row_to_json  # noqa: E402

WFS_URL = "https://datageo.ambiente.sp.gov.br/geoserver/datageo/ows"

FONTE = {
    "nome": "DataGeo SP - Camadas Ambientais",
    "orgao_responsavel": "Secretaria de Meio Ambiente, Infraestrutura e Logística de SP",
    "url_origem": WFS_URL,
    "formato": "WFS/GeoJSON",
    "periodicidade": "irregular",
    "escopo_geografico": "estadual",
    "licenca": "Dados Abertos (DataGeo)",
}

CAMADAS = [
    {
        "layer": "datageo:Areas_Protegidas_PI_DG_UCs_Protecao_Integral",
        "tema": "Unidades de Conservação Estaduais",
        "subtipo": "Proteção Integral",
        "id_fields": ("OBJECTID", "id", "gid"),
        "nome_fields": ("Unidade", "nome", "NOME"),
    },
    {
        "layer": "datageo:Areas_Protegidas_US_DG_UCs_Uso_Sustentavel",
        "tema": "Unidades de Conservação Estaduais",
        "subtipo": "Uso Sustentável",
        "id_fields": ("OBJECTID", "id", "gid"),
        "nome_fields": ("Unidade", "nome", "NOME"),
    },
]


def _selected_layers():
    targets = os.getenv("DATAGEO_SP_LAYERS")
    if not targets:
        return CAMADAS
    target_set = {t.strip() for t in targets.split(",") if t.strip()}
    return [cfg for cfg in CAMADAS if cfg["layer"] in target_set]


def _dataset_payload(layer_cfg: dict) -> dict:
    slug = layer_cfg["layer"].split(":")[-1].upper()
    today = date.today()
    return {
        "nome": f"DATAGEO_SP_{slug}_{today.isoformat()}",
        "descricao": f"{layer_cfg['tema']} - {layer_cfg['subtipo']} (camada {layer_cfg['layer']})",
        "versao": str(today.year),
        "data_referencia": today,
    }


def _prepare_rows(gdf, dataset_id: str, layer_cfg: dict):
    if gdf.empty:
        return []

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    elif gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)

    rows = []
    for _, row in gdf.iterrows():
        geom = ensure_multipolygon(row.geometry)
        if geom is None:
            continue
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "id_origem": str(pick(row, layer_cfg["id_fields"], row.name)),
                "dataset_id": dataset_id,
                "tema": layer_cfg["tema"],
                "subtipo": layer_cfg["subtipo"],
                "nome": pick(row, layer_cfg["nome_fields"]),
                "geom_wkt": geom.wkt,
                "atributos_json": row_to_json(row),
            }
        )
    return rows


def run():
    layers = _selected_layers()
    if not layers:
        print("[datageo_sp] Nenhuma camada configurada (ver DATAGEO_SP_LAYERS). Abortando.")
        return

    print("[datageo_sp] Iniciando ETL...")
    engine = get_engine()

    with engine.begin() as conn:
        fonte_id = get_or_create_fonte_dado(conn, **FONTE)

    for layer_cfg in layers:
        dataset_meta = _dataset_payload(layer_cfg)
        with engine.begin() as conn:
            dataset_id, is_new = get_or_create_dataset(conn, fonte_id, **dataset_meta)

        if not is_new:
            print(f"[datageo_sp] Dataset já importado para {layer_cfg['layer']}. Pulando.")
            continue

        print(f"[datageo_sp] Baixando camada {layer_cfg['layer']}...")
        gdf = fetch_wfs(WFS_URL, layer_cfg["layer"], batch_size=1000)
        if gdf.empty:
            print(f"[datageo_sp] Camada {layer_cfg['layer']} não retornou features.")
            continue

        rows = _prepare_rows(gdf, dataset_id, layer_cfg)
        if not rows:
            print(f"[datageo_sp] Nenhuma geometria válida em {layer_cfg['layer']}.")
            continue

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO camada_estadual_ambiental
                        (id, id_origem, dataset_id, tema, subtipo, nome, geom, atributos_json)
                    VALUES
                        (:id, :id_origem, :dataset_id, :tema, :subtipo, :nome,
                         ST_GeomFromText(:geom_wkt, 4326),
                         CAST(:atributos_json AS JSONB))
                    """
                ),
                rows,
            )

        print(f"[datageo_sp] {len(rows)} registros inseridos para {layer_cfg['layer']}.")


if __name__ == "__main__":
    run()
