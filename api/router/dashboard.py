# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.utils.basic_response import BasicResponse
from api.schemas.dashboard import DashboardCompleto
from api.router.controller.dashboard import DashboardHandler

router = APIRouter(
    tags=["Dashboard"],
    prefix="/dashboard",    
)

@router.get("/sp")
async def get_dashboard_sp_data(
    session: AsyncSession = Depends(SessionConnection.session)
) -> BasicResponse[DashboardCompleto]:
    return await DashboardHandler(session, sigla_estado="SP").execute()