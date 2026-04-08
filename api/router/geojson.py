# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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
    """,
}


@router.get("/")
async def list_layers():
    return {"layers": list(_LAYER_QUERIES.keys())}


@router.get("/{layer_name}")
async def get_layer_geojson(
    layer_name: str,
    session: AsyncSession = Depends(SessionConnection.session),
):
    query = _LAYER_QUERIES.get(layer_name)
    if query is None:
        raise HTTPException(
            status_code=404,
            detail=f"Layer '{layer_name}' not found. Available: {list(_LAYER_QUERIES.keys())}",
        )

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

    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": features,
    })
