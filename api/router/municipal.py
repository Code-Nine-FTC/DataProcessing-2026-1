# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from models.db_model import Municipio
from api.utils.basic_response import BasicResponse
from api.schemas.municipal import ResponseMunicipal
from api.router.controller.municipal_controller import MunicipalHandler

router = APIRouter(
    tags=["Municipal"],
    prefix="/municipal",    
)

@router.get("/")
async def get_all_municipal_data(session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session).execute()

@router.get("/geojson/layers")
async def list_geojson_layers() -> list[str]:
    return Municipio.GEOJSON_LAYERS

@router.get("/geojson/layers/{layer}")
async def get_geojson_layer(
    layer: str,
    municipio_id: Optional[int] = Query(None, description="Filtrar por ID do município"),
    session: AsyncSession = Depends(SessionConnection.session),
) -> JSONResponse:
    if layer not in Municipio.GEOJSON_LAYERS:
        raise HTTPException(
            status_code=404,
            detail=f"Camada '{layer}' não encontrada. Disponíveis: {Municipio.GEOJSON_LAYERS}",
        )
    data = await Municipio.get_geojson_layer(session, layer, municipio_id)
    return JSONResponse(content=data, media_type="application/geo+json")

@router.get("/{municipio_id}/estatisticas")
async def get_estatisticas_municipio(
    municipio_id: int,
    session: AsyncSession = Depends(SessionConnection.session),
) -> dict:
    from models.db_model import Municipio as MunicipioModel
    data = await MunicipioModel.get_estatisticas(session, municipio_id)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return data


@router.get("/{municipio_id}")
async def get_municipal_data_by_id(municipio_id: int, session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session, municipio_id).execute()
