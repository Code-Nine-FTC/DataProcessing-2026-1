# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from models.database import SessionConnection

router = APIRouter(
    tags=["GeoJSON Layers"],
    prefix="/municipal/geojson/layers",
)

_LAYER_QUERIES = {
    "municipios": """
        SELECT
            m.id::text AS id,
            m.nome,
            m.codigo_ibge,
            e.sigla AS estado_sigla,
            ST_AsGeoJSON(m.geom)::json AS geometry
        FROM municipio m
        JOIN estado e ON m.estado_id = e.id
        WHERE e.sigla = 'SP'
    """,
    "alertas_desmatamento": """
        SELECT
            d.id::text AS id,
            d.tipo_alerta AS nome,
            d.area_ha,
            d.data_ocorrencia::text AS data_ocorrencia,
            m.nome AS municipio,
            ST_AsGeoJSON(d.geom)::json AS geometry
        FROM desmatamento_alerta d
        LEFT JOIN municipio m ON d.municipio_id = m.id
        {filter_clause}
    """,
    "queimadas": """
        SELECT
            q.id::text AS id,
            q.fonte_sensor AS nome,
            q.intensidade,
            q.data_ocorrencia::text AS data_ocorrencia,
            q.bioma,
            q.dias_sem_chuva,
            q.precipitacao_mm,
            q.risco_fogo,
            m.nome AS municipio,
            ST_AsGeoJSON(q.geom)::json AS geometry
        FROM queimada_evento q
        LEFT JOIN municipio m ON q.municipio_id = m.id
        {filter_clause}
    """,
    "terras_indigenas": """
        SELECT
            t.id::text AS id,
            t.nome,
            t.fase,
            t.area_ha,
            m.nome AS municipio,
            ST_AsGeoJSON(t.geom)::json AS geometry
        FROM terra_indigena t
        LEFT JOIN municipio m ON t.municipio_id = m.id
        {filter_clause}
    """,
    "unidades_conservacao": """
        SELECT
            u.id::text AS id,
            u.nome,
            u.categoria,
            u.esfera,
            u.area_ha,
            m.nome AS municipio,
            ST_AsGeoJSON(u.geom)::json AS geometry
        FROM unidade_conservacao u
        LEFT JOIN municipio m ON u.municipio_id = m.id
        {filter_clause}
    """,
    "assentamentos": """
        SELECT
            a.id::text AS id,
            a.nome,
            a.modalidade,
            a.area_ha,
            m.nome AS municipio,
            ST_AsGeoJSON(a.geom)::json AS geometry
        FROM assentamento_rural a
        LEFT JOIN municipio m ON a.municipio_id = m.id
        {filter_clause}
    """,
    "quilombolas": """
        SELECT
            q.id::text AS id,
            q.nome,
            q.area_ha,
            m.nome AS municipio,
            ST_AsGeoJSON(q.geom)::json AS geometry
        FROM territorio_quilombola q
        LEFT JOIN municipio m ON q.municipio_id = m.id
        {filter_clause}
    """,
    "imoveis_rurais": """
        SELECT
            i.id::text AS id,
            i.nome_imovel AS nome,
            i.codigo_car,
            i.area_ha,
            i.situacao_cadastral,
            m.nome AS municipio,
            ST_AsGeoJSON(i.geom)::json AS geometry
        FROM imovel_rural i
        LEFT JOIN municipio m ON i.municipio_id = m.id
        {filter_clause}
    """,
}


@router.get("/")
async def list_layers():
    return {"layers": list(_LAYER_QUERIES.keys())}


_LAYER_ALIASES: dict[str, str] = {
    "alertas_desmatamento": "d",
    "queimadas": "q",
    "terras_indigenas": "t",
    "unidades_conservacao": "u",
    "assentamentos": "a",
    "quilombolas": "q",
    "imoveis_rurais": "i",
}


@router.get("/{layer_name}")
async def get_layer_geojson(
    layer_name: str,
    municipio_id: Optional[int] = Query(None, description="Filtrar features por município"),
    session: AsyncSession = Depends(SessionConnection.session),
):
    raw_query = _LAYER_QUERIES.get(layer_name)
    if raw_query is None:
        raise HTTPException(
            status_code=404,
            detail=f"Layer '{layer_name}' not found. Available: {list(_LAYER_QUERIES.keys())}",
        )

    if municipio_id is not None:
        if layer_name == "municipios":
            query = raw_query + f" AND m.id = {municipio_id}"
        else:
            alias = _LAYER_ALIASES.get(layer_name, "m")
            filter_clause = f"WHERE {alias}.municipio_id = {municipio_id}"
            query = raw_query.format(filter_clause=filter_clause)
    else:
        query = raw_query.replace("{filter_clause}", "")

    result = await session.execute(text(query))
    rows = result.mappings().all()

    features = []
    for row in rows:
        props = {k: v for k, v in row.items() if k != "geometry"}
        features.append({
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": props,
        })

    return JSONResponse(content=jsonable_encoder({
        "type": "FeatureCollection",
        "features": features,
    }))
