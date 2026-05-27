# -*- coding: utf-8 -*-
import asyncio
import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.utils.auth import require_admin
from models.db_model import Usuario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

_PIPELINES_DISPONIVEIS = [
    "icmbio", "funai", "incra", "palmares",
    "datageo_sp", "car", "inpe", "prodes_desmatamento",
]

# Registro em memória de jobs disparados nesta sessão
_jobs: Dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="etl")


# --- Schemas ---

class TriggerETLRequest(BaseModel):
    pipelines: Optional[List[str]] = None  # None = todas na ordem padrão


class JobStatus(BaseModel):
    job_id: str
    pipelines: List[str]
    status: Literal["pending", "running", "done", "failed"]
    iniciado_em: str
    finalizado_em: Optional[str] = None
    resultado: Optional[str] = None
    disparado_por: str


class TriggerETLResponse(BaseModel):
    job_id: str
    mensagem: str


# --- Helper ---

def _rodar_etl(job_id: str, pipelines: List[str]) -> None:
    """Executa o ETL de forma síncrona numa thread separada."""
    _jobs[job_id]["status"] = "running"

    # Adiciona data-ingestion ao path para importar os módulos ETL
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data-ingestion")
    base = os.path.abspath(base)
    if base not in sys.path:
        sys.path.insert(0, base)

    try:
        from core.config import AppConfig
        from etl.orchestrator import PipelineOrchestrator
        from sources.icmbio import create_pipeline as create_icmbio
        from sources.funai import create_pipeline as create_funai
        from sources.incra import create_pipeline as create_incra
        from sources.palmares import create_pipeline as create_palmares
        from sources.datageo_sp import create_pipeline as create_datageo_sp
        from sources.car import create_pipeline as create_car
        from sources.inpe import create_pipeline as create_inpe
        from sources.prodes_desmatamento import create_pipeline as create_prodes

        config = AppConfig.from_env()
        orchestrator = PipelineOrchestrator(config)

        factories = {
            "icmbio": create_icmbio, "funai": create_funai,
            "incra": create_incra, "palmares": create_palmares,
            "datageo_sp": create_datageo_sp, "car": create_car,
            "inpe": create_inpe, "prodes_desmatamento": create_prodes,
        }
        for nome, factory in factories.items():
            orchestrator.register_pipeline(nome, factory)

        successful, failed = orchestrator.run_all(pipelines)
        orchestrator.close()

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["resultado"] = f"{successful} sucesso(s), {failed} falha(s)"
    except Exception as exc:
        logger.exception("ETL job %s falhou", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["resultado"] = str(exc)
    finally:
        _jobs[job_id]["finalizado_em"] = datetime.now(timezone.utc).isoformat()


# --- Endpoints ---

@router.post(
    "/etl/trigger",
    response_model=TriggerETLResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispara pipelines de ingestão de dados em background",
)
async def trigger_etl(
    req: TriggerETLRequest,
    admin: Usuario = Depends(require_admin),
) -> TriggerETLResponse:
    pipelines = req.pipelines or _PIPELINES_DISPONIVEIS

    desconhecidas = [p for p in pipelines if p not in _PIPELINES_DISPONIVEIS]
    if desconhecidas:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipelines desconhecidas: {desconhecidas}. Disponíveis: {_PIPELINES_DISPONIVEIS}",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "pipelines": pipelines,
        "status": "pending",
        "iniciado_em": datetime.now(timezone.utc).isoformat(),
        "finalizado_em": None,
        "resultado": None,
        "disparado_por": admin.email,
    }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _rodar_etl, job_id, pipelines)

    logger.info("ETL job %s disparado por %s — pipelines: %s", job_id, admin.email, pipelines)
    return TriggerETLResponse(
        job_id=job_id,
        mensagem=f"Job iniciado. Acompanhe em GET /admin/etl/status/{job_id}",
    )


@router.get(
    "/etl/status/{job_id}",
    response_model=JobStatus,
    summary="Consulta o status de um job de ingestão",
)
async def status_etl(
    job_id: str,
    _: Usuario = Depends(require_admin),
) -> JobStatus:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    return JobStatus(**job)


@router.get(
    "/etl/jobs",
    response_model=List[JobStatus],
    summary="Lista todos os jobs de ingestão desta sessão",
)
async def listar_jobs(_: Usuario = Depends(require_admin)) -> List[JobStatus]:
    return [JobStatus(**j) for j in _jobs.values()]


@router.get(
    "/etl/pipelines",
    summary="Lista as pipelines disponíveis para trigger",
)
async def listar_pipelines(_: Usuario = Depends(require_admin)) -> dict:
    return {"pipelines": _PIPELINES_DISPONIVEIS}
