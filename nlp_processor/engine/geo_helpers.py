# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Text, cast, func, select

from models.db_model import Estado

_SP_GEOM = select(Estado.geom).where(Estado.sigla == "SP").scalar_subquery()
_TOLERANCE = 0.0002


def geom_as_geojson(geom_col: Any, simplify: Optional[float] = None) -> Any:
    geom = func.ST_Transform(geom_col, 4326)
    if simplify is not None:
        geom = func.ST_SimplifyPreserveTopology(geom, simplify)
    return cast(func.ST_AsGeoJSON(geom, 6), Text)


def geom_clipped_sp(geom_col: Any, simplify: Optional[float] = _TOLERANCE) -> Any:
    inter = func.ST_CollectionExtract(func.ST_Intersection(geom_col, _SP_GEOM), 3)
    clipped = func.ST_Transform(inter, 4326)
    if simplify is not None:
        clipped = func.ST_SimplifyPreserveTopology(clipped, simplify)
    return cast(func.ST_AsGeoJSON(clipped, 6), Text)


def geom_clipped_municipio(geom_col: Any, mun_geom: Any, simplify: Optional[float] = _TOLERANCE) -> Any:
    inter = func.ST_CollectionExtract(
        func.ST_Intersection(func.ST_MakeValid(geom_col), mun_geom), 3
    )
    clipped = func.ST_Transform(inter, 4326)
    if simplify is not None:
        clipped = func.ST_SimplifyPreserveTopology(clipped, simplify)
    return cast(func.ST_AsGeoJSON(clipped, 6), Text)


def geom_intersection(geom_a: Any, geom_b: Any, simplify: Optional[float] = _TOLERANCE) -> Any:
    inter = func.ST_CollectionExtract(
        func.ST_Intersection(func.ST_MakeValid(geom_a), func.ST_MakeValid(geom_b)), 3
    )
    inter = func.ST_Transform(inter, 4326)
    if simplify is not None:
        inter = func.ST_SimplifyPreserveTopology(inter, simplify)
    return cast(func.ST_AsGeoJSON(inter, 6), Text)


def build_bbox(features: list[dict]) -> Optional[list[float]]:
    coords: list[tuple[float, float]] = []

    def _extract(geom: dict) -> None:
        t = geom.get("type", "")
        c = geom.get("coordinates")
        if c is None:
            return
        if t == "Point":
            coords.append((c[0], c[1]))
        elif t in ("LineString", "MultiPoint"):
            coords.extend((p[0], p[1]) for p in c)
        elif t in ("Polygon", "MultiLineString"):
            for ring in c:
                coords.extend((p[0], p[1]) for p in ring)
        elif t == "MultiPolygon":
            for poly in c:
                for ring in poly:
                    coords.extend((p[0], p[1]) for p in ring)

    for f in features:
        if f.get("geometry"):
            _extract(f["geometry"])

    if not coords:
        return None
    xs, ys = zip(*coords)
    return [min(xs), min(ys), max(xs), max(ys)]


def stmt_para_sql(stmt: Any) -> Optional[str]:
    from sqlalchemy.dialects import postgresql
    try:
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        return str(compiled)
    except Exception:
        return str(stmt)


def fmt_int(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def round_float(value: Any, ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (ValueError, TypeError):
        return None
