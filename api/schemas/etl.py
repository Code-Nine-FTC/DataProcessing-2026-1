# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from pydantic import ConfigDict


class EtlStepStatus(BaseModel):
    id: UUID
    pipeline_name: str
    etapa: str
    status: str
    detalhes: Optional[str] = None
    total_registros: int
    registros_inseridos: int
    data_inicio: datetime
    data_fim: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class EtlStatusResponse(BaseModel):
    status_atual: str 
    ultima_atualizacao: datetime
    passos: List[EtlStepStatus]

class EtlTriggerRequest(BaseModel):
    pipelines: Optional[List[str]] = Field(None, description="Lista de pipelines para rodar. Se nulo, roda todas.")
