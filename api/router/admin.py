# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import SessionConnection
from api.schemas.etl import EtlStatusResponse, EtlTriggerRequest
from api.services.etl_service import EtlService
from api.utils.basic_response import BasicResponse

router = APIRouter(
    tags=["Admin & ETL"],
    prefix="/admin/etl",
)

# Singleton service to track state
_etl_service = EtlService()

@router.get("/status", response_model=BasicResponse[EtlStatusResponse])
async def get_etl_status(
    session: AsyncSession = Depends(SessionConnection.session)
):
    """
    Retorna o status atual do processo de ETL e o histórico das últimas etapas.
    """
    status_data = await _etl_service.get_status(session)
    return BasicResponse(data=status_data)

@router.post("/atualizar", status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_update(
    req: EtlTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Inicia o processo de atualização manual do banco de dados (ETL).
    O processo roda em segundo plano.
    """
    background_tasks.add_task(_etl_service.run_manual_update, req.pipelines)
    return {"message": "Processo de atualização iniciado em segundo plano."}
