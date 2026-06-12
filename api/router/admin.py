# -*- coding: utf-8 -*-
import asyncio
import json
import logging
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.etl import EtlStatusResponse, EtlTriggerRequest
from api.services.auth_service import AuthService, decodificar_token
from api.services.etl_service import EtlService
from api.utils.auth import require_admin
from api.utils.basic_response import BasicResponse
from celery_app import run_etl_update_task
from models.database import Database, SessionConnection
from models.db_model import Usuario

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Admin & ETL"],
    prefix="/admin/etl",
    dependencies=[Depends(require_admin)],
)

ws_router = APIRouter(tags=["Admin & ETL WS"], prefix="/admin/etl")

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

_POLL_RUNNING_SECS = 3
_POLL_IDLE_SECS = 10


@ws_router.websocket("/ws")
async def etl_status_ws(
    websocket: WebSocket,
    token: str = Query(..., description="JWT de autenticação do administrador"),
):
    """
    Abre uma conexão WebSocket que transmite atualizações de status do ETL.

    O cliente deve enviar o JWT via query param: `?token=<jwt>`.
    Mensagens JSON enviadas pelo servidor:
      {"status_atual": "RUNNING"|"COMPLETED"|"FAILED"|"IDLE",
       "ultima_atualizacao": "<ISO datetime>"}

    Códigos de fechamento:
      4001 — token inválido/expirado
      4003 — usuário não é administrador
    """
    await websocket.accept()

    payload = decodificar_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Token inválido ou expirado")
        return

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        await websocket.close(code=4001, reason="Token malformado")
        return

    async with Database().session as session:
        usuario: Usuario | None = await AuthService(session).buscar_por_id(user_id)

    if usuario is None or usuario.role != "admin":
        await websocket.close(code=4003, reason="Acesso negado: requer perfil admin")
        return

    logger.info("WebSocket ETL conectado: usuário %s", usuario.email)

    etl_service = EtlService()
    ultimo_status: str | None = None

    try:
        while True:
            async with Database().session as session:
                status_data = await etl_service.get_status(session)

            status_atual: str = status_data["status_atual"]
            ultima_atualizacao = status_data["ultima_atualizacao"]

            if status_atual != ultimo_status:
                ultimo_status = status_atual
                await websocket.send_text(
                    json.dumps({
                        "status_atual": status_atual,
                        "ultima_atualizacao": ultima_atualizacao.isoformat(),
                    })
                )

            intervalo = _POLL_RUNNING_SECS if status_atual == "RUNNING" else _POLL_IDLE_SECS
            await asyncio.sleep(intervalo)

    except WebSocketDisconnect:
        logger.info("WebSocket ETL desconectado: usuário %s", usuario.email)
    except Exception:
        logger.exception("Erro no WebSocket ETL para usuário %s", usuario.email)
