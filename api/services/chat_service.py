# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.chat import (
    ChatHistoricoResponse,
    ChatMensagemRequest,
    ChatMensagemResponse,
    ChatResumo,
    FeatureCollection,
    FeedbackRequest,
    FonteCitada,
    MensagemHistorico,
)
from models.db_model import Chat, ConsultaUsuario, FeedbackResposta, RespostaSistema
from nlp_processor.index import NLPProcessor

logger = logging.getLogger(__name__)

_processor = NLPProcessor()


class ChatService:
    # ------------------------------------------------------------------
    # Enviar mensagem
    # ------------------------------------------------------------------

    async def enviar_mensagem(
        self,
        req: ChatMensagemRequest,
        session: AsyncSession,
    ) -> ChatMensagemResponse:
        result = await _processor.process(
            session=session,
            pergunta=req.pergunta,
            chat_id=req.chat_id,
        )

        mapa_raw = result["mapa"]
        mapa = FeatureCollection(**mapa_raw)

        fontes = [FonteCitada(**f) for f in result["fontes_citadas"]]

        return ChatMensagemResponse(
            chat_id=result["chat_id"],
            consulta_id=result["consulta_id"],
            resposta_id=result["resposta_id"],
            texto_resposta=result["texto_resposta"],
            fontes_citadas=fontes,
            mapa=mapa,
            bbox=result["bbox"],
            status=result["status"],
        )

    # ------------------------------------------------------------------
    # Listar chats
    # ------------------------------------------------------------------

    async def listar_chats(self, session: AsyncSession) -> list[ChatResumo]:
        stmt = select(Chat).order_by(Chat.created_at.desc()).limit(50)
        rows = (await session.execute(stmt)).scalars().all()
        return [ChatResumo(id=c.id, title=c.title) for c in rows]

    # ------------------------------------------------------------------
    # Histórico de um chat
    # ------------------------------------------------------------------

    async def historico_chat(
        self, chat_id: UUID, session: AsyncSession
    ) -> ChatHistoricoResponse:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Chat não encontrado.")

        stmt = (
            select(ConsultaUsuario, RespostaSistema)
            .join(
                RespostaSistema,
                RespostaSistema.consulta_usuario_id == ConsultaUsuario.id,
                isouter=True,
            )
            .where(ConsultaUsuario.chat_id == chat_id)
            .order_by(ConsultaUsuario.turno)
        )
        rows = (await session.execute(stmt)).all()

        mensagens = []
        for consulta, resposta in rows:
            fontes: list[FonteCitada] = []
            if resposta and resposta.fontes_utilizadas_json:
                for f in resposta.fontes_utilizadas_json.get("fontes", []):
                    fontes.append(FonteCitada(**f))

            mensagens.append(
                MensagemHistorico(
                    consulta_id=consulta.id,
                    pergunta=consulta.pergunta or "",
                    resposta=resposta.texto_resposta if resposta else None,
                    turno=consulta.turno or 0,
                    fontes=fontes,
                )
            )

        return ChatHistoricoResponse(
            chat_id=chat.id,
            title=chat.title,
            mensagens=mensagens,
        )

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    async def registrar_feedback(
        self, req: FeedbackRequest, session: AsyncSession
    ) -> dict:
        resposta = await session.get(RespostaSistema, req.resposta_sistema_id)
        if resposta is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Resposta não encontrada.")

        feedback = FeedbackResposta(
            resposta_sistema_id=req.resposta_sistema_id,
            avaliacao=req.avaliacao,
            comentario=req.comentario,
        )
        session.add(feedback)
        await session.commit()
        return {"mensagem": "Feedback registrado com sucesso."}
