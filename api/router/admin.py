# -*- coding: utf-8 -*-
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.etl import EtlStatusResponse, EtlTriggerRequest
from api.services.etl_service import EtlService
from api.utils.auth import require_admin
from api.utils.basic_response import BasicResponse
from celery_app import run_etl_update_task
from models.database import SessionConnection

router = APIRouter(
    tags=["Admin & ETL"],
    prefix="/admin/etl",
    dependencies=[Depends(require_admin)],
)
def get_etl_service() -> EtlService:
    return EtlService()


@router.get("/status", response_model=BasicResponse[EtlStatusResponse])
async def get_etl_status(
    session: AsyncSession = Depends(SessionConnection.session),
    etl_service: EtlService = Depends(get_etl_service)
):
    """
    Retorna o status atual do processo de ETL e o histórico das últimas etapas.
    """

    raw_status_data = await etl_service.get_status(session)

    validated_status = EtlStatusResponse.model_validate(raw_status_data)
    
    return BasicResponse(data=validated_status)

@router.post(
    "/atualizar", 
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, str]
)
async def trigger_manual_update(
    req: EtlTriggerRequest
):
    """
    Inicia o processo de atualização manual do banco de dados (ETL).
    A tarefa é enfileirada no Celery para execução assíncrona em um worker separado.
    """
    task = run_etl_update_task.delay(req.pipelines)
    
    return {
        "message": "Processo de atualização enfileirado com sucesso.",
        "task_id": task.id
    }
