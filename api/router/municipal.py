# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.utils.basic_response import BasicResponse
from api.schemas.municipal import ResponseMunicipal, ResponseMunicipioSearch, GeoJSONGeometry, ResponseImovelRuralIntersection
from api.router.controller.municipal_controller import MunicipalHandler, MunicipioSearchHandler, IntersectionHandler

router = APIRouter(
    tags=["Municipal"],
    prefix="/municipal",    
)

@router.get("/")
async def get_all_municipal_data(session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session).execute()

@router.get("/search", response_model=BasicResponse[list[ResponseMunicipioSearch]])
async def search_municipios(
    q: str = Query("", description="Termo de busca por nome do município"),
    estado_sigla: str = Query(None, description="Filtrar por UF (ex: SP)"),
    session: AsyncSession = Depends(SessionConnection.session)
) -> BasicResponse[list[ResponseMunicipioSearch]]:
    return await MunicipioSearchHandler(session, search=q, estado_sigla=estado_sigla).execute()

@router.get("/{municipio_id}")
async def get_municipal_data_by_id(municipio_id: int, session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session, municipio_id).execute()

@router.post("/intersections")
async def get_intersecting_imoveis(
    geojson_geometry: GeoJSONGeometry,
    session: AsyncSession = Depends(SessionConnection.session)
) -> BasicResponse[list[ResponseImovelRuralIntersection]]:
    return await IntersectionHandler(session, geojson_geometry).execute()