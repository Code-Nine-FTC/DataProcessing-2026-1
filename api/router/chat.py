# -*- coding: utf-8 -*-
from typing import AsyncGenerator, List
from uuid import UUID

from fastapi import APIRouter, Depends, status
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

router = APIRouter(prefix="/chat", tags=["Chat Ambiental NLP"])

_service = ChatService()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionConnection.session() as session:
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
    "/{chat_id}/historico",
    response_model=ChatHistoricoResponse,
    summary="Retorna o histórico de mensagens de um chat",
)
async def historico_chat(
    chat_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ChatHistoricoResponse:
    return await _service.historico_chat(chat_id, session)


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
