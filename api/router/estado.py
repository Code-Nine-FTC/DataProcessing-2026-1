# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.utils.basic_response import BasicResponse
from api.schemas.estado import ResponseEstado, ResponseMunicipioSimples
from api.router.controller.estado_controller import EstadoHandler

router = APIRouter(
    tags=["Estado"],
    prefix="/estado",
)


@router.get("/")
async def list_estados(
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[list[ResponseEstado]]:
    return await EstadoHandler(session).execute_list()


@router.get("/{estado_id}/municipios")
async def get_municipios_por_estado(
    estado_id: int,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[list[ResponseMunicipioSimples]]:
    return await EstadoHandler(session, estado_id).execute_municipios()
