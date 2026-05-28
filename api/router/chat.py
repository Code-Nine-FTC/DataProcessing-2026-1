# -*- coding: utf-8 -*-
from typing import AsyncGenerator, List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.chat import (
    ChatHistoricoResponse,
    ChatMensagemRequest,
    ChatMensagemResponse,
    ChatResumo,
    FeedbackRequest,
)
from api.services.chat_service import ChatService
from models.database import SessionConnection
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat Ambiental NLP"])

_service = ChatService()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in SessionConnection.session():
        yield session


@router.post(
    "/mensagem",
    response_model=ChatMensagemResponse,
    status_code=status.HTTP_200_OK,
    summary="Envia uma mensagem ao agente ambiental",
    description=(
        "Processa a pergunta do usuário sobre o ambiente de São Paulo, "
        "consulta as fontes disponíveis no sistema e retorna texto de resposta "
        "com citação de fontes e dados GeoJSON prontos para exibição no Leaflet."
    ),
)
async def enviar_mensagem(
    req: ChatMensagemRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatMensagemResponse:
    return await _service.enviar_mensagem(req, session)


@router.get(
    "/",
    response_model=List[ChatResumo],
    summary="Lista os chats existentes",
)
async def listar_chats(
    session: AsyncSession = Depends(get_session),
) -> List[ChatResumo]:
    return await _service.listar_chats(session)


@router.get(
    "/resposta/{resposta_id}/geojson",
    summary="Retorna o GeoJSON persistido de uma resposta do sistema",
    description=(
        "Útil no QGIS como fonte HTTP (vetor). O conteúdo é o mesmo de `resposta_sistema.mapa_geojson` "
        "e do campo «mapa» na mesma rodada. Identifique a rodada pelo `resposta_id` retornado em "
        "`POST /chat/mensagem` ou em cada item de `GET /chat/{chat_id}/historico`."
    ),
    responses={404: {"description": "Resposta inexistente ou sem mapa gravado."}},
)
async def geojson_resposta(
    resposta_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    payload = await _service.geojson_por_resposta(resposta_id, session)
    return JSONResponse(content=payload, media_type="application/geo+json")


@router.get(
    "/{chat_id}/historico",
    response_model=ChatHistoricoResponse,
    summary="Retorna o histórico de mensagens de um chat",
    description=(
        "Cada item em «mensagens» pode incluir «resposta_id», «mapa» (GeoJSON do banco) e «qgis» "
        "(«geojson_url_path» aponta para GET /chat/resposta/{resposta_id}/geojson daquela rodada). "
        "No nível raiz, «mapa»/«bbox»/«status» repetem a última resposta."
    ),
)
async def historico_chat(
    chat_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ChatHistoricoResponse:
    return await _service.historico_chat(chat_id, session)


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_200_OK,
    summary="Desativa (soft delete) um chat",
)
async def desativar_chat(
    chat_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _service.desativar_chat(chat_id, session)


@router.post(
    "/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Registra feedback (👍/👎) em uma resposta do sistema",
)
async def registrar_feedback(
    req: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _service.registrar_feedback(req, session)


class ResumoResponse(BaseModel):
    resumo: str
    fontes: List[dict] = []

@router.get(
    "/{chat_id}/resumo",
    response_model=ResumoResponse,
    summary="Gera um relatório condensado do chat via IA",
)
async def resumo_chat(
    chat_id: UUID,
    session: AsyncSession = Depends(get_session),
):

    dados_relatorio = await _service.gerar_resumo_relatorio(chat_id, session)
    return ResumoResponse(resumo=dados_relatorio["resumo"], fontes=dados_relatorio["fontes"])