# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMensagemRequest(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=2000, description="Pergunta do usuário")
    chat_id: Optional[UUID] = Field(None, description="ID do chat existente. Null para iniciar novo.")


class FeedbackRequest(BaseModel):
    resposta_sistema_id: UUID
    avaliacao: int = Field(..., ge=-1, le=1, description="-1 ruim, 0 neutro, 1 bom")

class MapGeometry(BaseModel):
    type: str
    coordinates: Any


class MapFeature(BaseModel):
    type: str = "Feature"
    geometry: Optional[MapGeometry]
    properties: Dict[str, Any]


class FeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[MapFeature]


class FeedbackInfo(BaseModel):
    id: UUID
    avaliacao: int = Field(description="-1 ruim, 0 neutro, 1 bom")

class FonteCitada(BaseModel):
    nome: str
    orgao: Optional[str] = None
    url: Optional[str] = None


class ChatMensagemResponse(BaseModel):
    chat_id: UUID
    consulta_id: UUID
    resposta_id: UUID
    texto_resposta: str
    fontes_citadas: List[FonteCitada]
    mapa: FeatureCollection
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [minLng, minLat, maxLng, maxLat] para ajuste da câmera Leaflet.",
    )
    status: str = Field(description="sucesso | sem_resultado | fora_escopo | erro")

class ChatResumo(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: Optional[datetime] = None


class MensagemHistorico(BaseModel):
    consulta_id: UUID
    resposta_id: Optional[UUID] = None
    pergunta: str
    resposta: Optional[str] = None
    turno: int
    fontes: List[FonteCitada] = []
    feedback: Optional[FeedbackInfo] = None


class ChatHistoricoResponse(BaseModel):
    chat_id: UUID
    title: Optional[str] = None
    mensagens: List[MensagemHistorico]
