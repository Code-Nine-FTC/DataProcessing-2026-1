# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.utils.basic_response import BasicResponse
from api.schemas.municipal import ResponseMunicipal, GeoJSONGeometry, ResponseImovelRuralIntersection
from api.router.controller.municipal_controller import MunicipalHandler, IntersectionHandler

router = APIRouter(
    tags=["Municipal"],
    prefix="/municipal",    
)

@router.get("/")
async def get_all_municipal_data(session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session).execute()

@router.get("/{municipio_id}")
async def get_municipal_data_by_id(municipio_id: int, session: AsyncSession = Depends(SessionConnection.session)) -> BasicResponse[list[ResponseMunicipal]]:
    return await MunicipalHandler(session, municipio_id).execute()

@router.post("/intersections")
async def get_intersecting_imoveis(
    geojson_geometry: GeoJSONGeometry,
    session: AsyncSession = Depends(SessionConnection.session)
) -> BasicResponse[list[ResponseImovelRuralIntersection]]:
    return await IntersectionHandler(session, geojson_geometry).execute()