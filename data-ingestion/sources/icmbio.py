"""
ETL: Unidades de Conservação — ICMBio / TerraBrasilis (INPE)
Fonte:  TerraBrasilis WFS — camadas de UC por bioma
        http://terrabrasilis.dpi.inpe.br/geoserver/wfs
Tabela: unidade_conservacao

Nota: o GeoServer do MMA (geoservicos.mma.gov.br) estava fora do ar.
      Usamos o espelho do TerraBrasilis/INPE que mantém as mesmas UCs
      organizadas por bioma; deduplicamos por id_origem para evitar
      contar duas vezes UCs que atravessam mais de um bioma.
"""
import io
import sys
import uuid
from datetime import date

import geopandas as gpd
import pandas as pd
import requests
from sqlalchemy import text

sys.path.insert(0, ".")
sys.path.insert(0, "data-ingestion")
from models.database import get_engine
from loader import get_or_create_fonte_dado, get_or_create_dataset
from utils import ensure_multipolygon, row_to_json, pick

WFS_URL = "http://terrabrasilis.dpi.inpe.br/geoserver/wfs"

# Uma camada por bioma — TerraBrasilis não suporta paginação WFS 2.0 nessas
# camadas (sem PK), então usamos WFS 1.1.0 com maxFeatures alto de uma vez.
BIOME_LAYERS = [
    "prodes-amazon-nb:conservation_units_amazon_biome",
    "prodes-cerrado-nb:conservation_units_cerrado_biome",
    "prodes-mata-atlantica-nb:conservation_units_mata_atlantica_biome",
    "prodes-caatinga-nb:conservation_units_caatinga_biome",
    "prodes-pampa-nb:conservation_units_pampa_biome",
    "prodes-pantanal-nb:conservation_units_pantanal_biome",
]

FONTE = {
    "nome": "ICMBio - Unidades de Conservação",
    "orgao_responsavel": "Instituto Chico Mendes de Conservação da Biodiversidade",
    "url_origem": WFS_URL,
    "formato": "WFS/GeoJSON",
    "periodicidade": "anual",
    "escopo_geografico": "nacional",
    "licenca": "CC BY 4.0",
}

DATASET = {
    "nome": "UC_TERRABRASILIS",
    "descricao": "Unidades de Conservação do Brasil - TerraBrasilis/INPE (espelho ICMBio)",
    "versao": str(date.today().year),
    "data_referencia": date.today(),
}


_NOME      = ("nome", "NOME", "nm_uc", "NM_UC", "nome_uc", "name")
_CATEGORIA = ("categoria", "CATEGORIA", "cat", "CAT_UC", "nome_cat")
_ESFERA    = ("esfera", "ESFERA", "esfera_gov", "ESFERA_GOV")
_GRUPO     = ("grupo", "GRUPO", "grupo_uc", "GRUPO_STATUS", "DS_GRUPO_STATUS")
_ID_ORIG   = ("id", "ID", "gid", "FID", "objectid", "cod_uc")


def _fetch_biome_layer(layer: str) -> gpd.GeoDataFrame:
    """Baixa uma camada UC do TerraBrasilis via WFS 1.1.0 (sem paginação)."""
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "maxFeatures": 10000,
    }
    resp = requests.get(WFS_URL, params=params, timeout=120)
    resp.raise_for_status()
    return gpd.read_file(io.BytesIO(resp.content))


def run():
    print("[icmbio] Iniciando ETL...")
    engine = get_engine()

    # 1. Baixar dados antes de abrir transação
    gdfs = []
    for layer in BIOME_LAYERS:
        print(f"[icmbio] Baixando camada: {layer}...")
        gdf_biome = _fetch_biome_layer(layer)
        print(f"  → {len(gdf_biome)} features")
        gdfs.append(gdf_biome)

    gdf = pd.concat(gdfs, ignore_index=True)
    print(f"[icmbio] Total bruto (com sobreposição de biomas): {len(gdf)}")

    # Deduplica por id_origem (mesma UC pode aparecer em múltiplos biomas)
    id_col = next((c for c in _ID_ORIG if c in gdf.columns), None)
    if id_col:
        gdf = gdf.drop_duplicates(subset=[id_col])
    print(f"[icmbio] Após deduplicação: {len(gdf)}")

    gdf = gdf.to_crs(epsg=4326)
    print("[icmbio] Preparando inserção...")

    # 2. Preparar rows com nomes normalizados
    rows = []
    for _, row in gdf.iterrows():
        geom = ensure_multipolygon(row.geometry)
        rows.append({
            "id": str(uuid.uuid4()),
            "id_origem": str(pick(row, _ID_ORIG, row.name)),
            "dataset_id": None,  # preenchido após criar dataset
            "nome": pick(row, _NOME),
            "categoria": pick(row, _CATEGORIA),
            "esfera": pick(row, _ESFERA),
            "grupo_snuc": pick(row, _GRUPO),
            "area_ha": None,  # não disponível nesta fonte
            "geom_wkt": geom.wkt if geom else None,
            "atributos_json": row_to_json(row),
        })

    # 3. Tudo numa única transação — se o INSERT falhar, dataset não é commitado
    with engine.begin() as conn:
        fonte_id = get_or_create_fonte_dado(conn, **FONTE)
        dataset_id, is_new = get_or_create_dataset(conn, fonte_id, **DATASET)

        if not is_new:
            return

        for r in rows:
            r["dataset_id"] = dataset_id

        conn.execute(
            text("""
                INSERT INTO unidade_conservacao
                    (id, id_origem, dataset_id, nome, categoria, esfera,
                     grupo_snuc, area_ha, geom, atributos_json)
                VALUES
                    (:id, :id_origem, :dataset_id, :nome, :categoria, :esfera,
                     :grupo_snuc, :area_ha,
                     ST_GeomFromText(:geom_wkt, 4326),
                     CAST(:atributos_json AS JSONB))
            """),
            rows,
        )

    print(f"[icmbio] {len(rows)} registros inseridos.")


if __name__ == "__main__":
    run()
