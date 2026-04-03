import io
import json
import math

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import MultiPolygon, Polygon, GeometryCollection
from shapely.validation import make_valid

# Palmares e INCRA usam WFS 1.1.0 que não suporta startIndex,
# então eu adicionei um parâmetro para forçar o uso do método antigo de paginação.
def fetch_wfs(base_url: str, layer: str, batch_size: int = 500, wfs_version: str = "2.0.0") -> gpd.GeoDataFrame:
    """Baixa todas as features de um WFS com paginação automática (WFS 2.0 startIndex)."""
    gdfs, start = [], 0
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": batch_size,
    }
    while True:
        params["startIndex"] = start
        print(f"  → features {start}–{start + batch_size}...")
        resp = requests.get(base_url, params=params, timeout=120)
        resp.raise_for_status()
        chunk = gpd.read_file(io.BytesIO(resp.content))
        if chunk.empty:
            break
        gdfs.append(chunk)
        start += len(chunk)
        if len(chunk) < batch_size:
            break

    if not gdfs:
        return gpd.GeoDataFrame()
    return pd.concat(gdfs, ignore_index=True)


def ensure_multipolygon(geom):
    """Garante que a geometria é um MultiPolygon (converte Polygon se necessário) e corrige geometrias inválidas."""
    if geom is None or geom.is_empty:
        return None
        
    if not geom.is_valid:
        geom = make_valid(geom)
        
    if geom.is_empty:
        return None
        
    if geom.geom_type == "GeometryCollection":
        polygons = []
        for g in geom.geoms:
            if g.geom_type in ("Polygon", "MultiPolygon"):
                polygons.append(g)
        if not polygons:
            return None
        # Convert to a single MultiPolygon containing all extracted polygon parts
        multi_parts = []
        for p in polygons:
            if p.geom_type == "Polygon":
                multi_parts.append(p)
            else:
                multi_parts.extend(p.geoms)
        return MultiPolygon(multi_parts) if multi_parts else None
        
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    elif geom.geom_type == "MultiPolygon":
        return geom
        
    return None


def safe_float(val, null_sentinel: float = None) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f):
            return None
        if null_sentinel is not None and f == null_sentinel:
            return None
        return f
    except (TypeError, ValueError):
        return None


def safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def row_to_json(row: pd.Series) -> str:
    """Serializa uma linha do GeoDataFrame (sem geometry) para string JSON."""
    d = {}
    for k, v in row.items():
        if k == "geometry":
            continue
        if isinstance(v, np.integer):
            d[k] = int(v)
        elif isinstance(v, np.floating):
            d[k] = None if np.isnan(v) else float(v)
        elif isinstance(v, np.bool_):
            d[k] = bool(v)
        else:
            try:
                if pd.isna(v):
                    d[k] = None
                    continue
            except (TypeError, ValueError):
                pass
            d[k] = v
    return json.dumps(d, default=str)


def pick(row: pd.Series, candidates: tuple, default=None):
    """Retorna o primeiro valor não-nulo encontrado entre os nomes candidatos."""
    for c in candidates:
        v = row.get(c)
        if v is not None and str(v).strip() not in ("", "nan", "None"):
            return v
    return default
