# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.utils.basic_response import BasicResponse
from api.schemas.imovel import ResponseImovel, ResponseQueimadaRelacao, ResponseDesmatamentoRelacao
from api.router.controller.imovel_controller import ImovelHandler

router = APIRouter(
    tags=["Imóvel Rural"],
    prefix="/imovel",
)


@router.get("/{imovel_id}")
async def get_imovel(
    imovel_id: str,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[ResponseImovel]:
    return await ImovelHandler(session, imovel_id).execute_detail()


@router.get("/{imovel_id}/queimadas")
async def get_queimadas_do_imovel(
    imovel_id: str,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[list[ResponseQueimadaRelacao]]:
    return await ImovelHandler(session, imovel_id).execute_queimadas()


@router.get("/{imovel_id}/desmatamentos")
async def get_desmatamentos_do_imovel(
    imovel_id: str,
    session: AsyncSession = Depends(SessionConnection.session),
) -> BasicResponse[list[ResponseDesmatamentoRelacao]]:
    return await ImovelHandler(session, imovel_id).execute_desmatamentos()
