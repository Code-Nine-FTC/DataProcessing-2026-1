# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class EtlStepStatus(BaseModel):
    pipeline_name: str
    etapa: str
    status: str
    detalhes: Optional[str] = None
    data_inicio: datetime
    data_fim: Optional[datetime] = None
    total_registros: int = 0
    registros_inseridos: int = 0

class EtlStatusResponse(BaseModel):
    status_atual: str # 'IDLE', 'RUNNING', 'COMPLETED', 'FAILED'
    ultima_atualizacao: datetime
    passos: List[EtlStepStatus]

class EtlTriggerRequest(BaseModel):
    pipelines: Optional[List[str]] = Field(None, description="Lista de pipelines para rodar. Se nulo, roda todas.")
