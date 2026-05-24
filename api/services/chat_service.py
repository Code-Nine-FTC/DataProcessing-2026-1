# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.chat import (
    ChatHistoricoResponse,
    ChatMensagemRequest,
    ChatMensagemResponse,
    ChatResumo,
    FeatureCollection,
    FeedbackInfo,
    FeedbackRequest,
    FonteCitada,
    MensagemHistorico,
)
from api.utils.qgis_integracao import montar_integracao_qgis
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
            municipio=req.municipio,
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
            qgis=montar_integracao_qgis(result["resposta_id"]),
        )

    # ------------------------------------------------------------------
    # Listar chats
    # ------------------------------------------------------------------

    async def listar_chats(self, session: AsyncSession) -> list[ChatResumo]:
        stmt = (
            select(Chat)
            .where(Chat.ativo == True)
            .order_by(Chat.created_at.desc().nullslast())
            .limit(50)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            ChatResumo(id=c.id, title=c.title, created_at=c.created_at, ativo=c.ativo)
            for c in rows
        ]

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
            select(ConsultaUsuario, RespostaSistema, FeedbackResposta)
            .join(
                RespostaSistema,
                RespostaSistema.consulta_usuario_id == ConsultaUsuario.id,
                isouter=True,
            )
            .join(
                FeedbackResposta,
                FeedbackResposta.resposta_sistema_id == RespostaSistema.id,
                isouter=True,
            )
            .where(ConsultaUsuario.chat_id == chat_id)
            .order_by(ConsultaUsuario.turno)
        )
        rows = (await session.execute(stmt)).all()

        mensagens = []
        for consulta, resposta, feedback in rows:
            fontes: list[FonteCitada] = []
            if resposta and resposta.fontes_utilizadas_json:
                for f in resposta.fontes_utilizadas_json.get("fontes", []):
                    fontes.append(FonteCitada(**f))

            feedback_info = None
            if feedback:
                feedback_info = FeedbackInfo(
                    id=feedback.id,
                    avaliacao=feedback.avaliacao,
                )

            mapa_turno: Optional[FeatureCollection] = None
            if resposta and resposta.mapa_geojson:
                mapa_turno = FeatureCollection(**resposta.mapa_geojson)

            mensagens.append(
                MensagemHistorico(
                    consulta_id=consulta.id,
                    resposta_id=resposta.id if resposta else None,
                    pergunta=consulta.pergunta or "",
                    resposta=resposta.texto_resposta if resposta else None,
                    turno=consulta.turno or 0,
                    fontes=fontes,
                    feedback=feedback_info,
                    mapa=mapa_turno,
                    qgis=montar_integracao_qgis(resposta.id) if resposta else None,
                )
            )

        # Extrair mapa, bbox e status da última resposta
        mapa = None
        bbox = None
        last_status = None
        if rows:
            last_resposta = rows[-1][1]
            if last_resposta:
                if last_resposta.mapa_geojson:
                    mapa = FeatureCollection(**last_resposta.mapa_geojson)
                if last_resposta.bbox_resultado is not None:
                    shape = to_shape(last_resposta.bbox_resultado)
                    bbox = list(shape.bounds)
                last_status = last_resposta.status

        return ChatHistoricoResponse(
            chat_id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            mensagens=mensagens,
            mapa=mapa,
            bbox=bbox,
            status=last_status,
        )

    # ------------------------------------------------------------------
    # GeoJSON de uma resposta (QGIS via HTTP)
    # ------------------------------------------------------------------

    async def geojson_por_resposta(
        self, resposta_id: UUID, session: AsyncSession
    ) -> dict:
        from fastapi import HTTPException

        resposta = await session.get(RespostaSistema, resposta_id)
        if resposta is None or not resposta.mapa_geojson:
            raise HTTPException(
                status_code=404,
                detail="Resposta não encontrada ou sem GeoJSON armazenado.",
            )
        return resposta.mapa_geojson

    # ------------------------------------------------------------------
    # Desativar chat (soft delete)
    # ------------------------------------------------------------------

    async def desativar_chat(
        self, chat_id: UUID, session: AsyncSession
    ) -> dict:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Chat não encontrado.")

        chat.ativo = False
        await session.commit()
        return {"mensagem": "Chat desativado com sucesso."}

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
        )
        session.add(feedback)
        await session.commit()
        return {"mensagem": "Feedback registrado com sucesso."}
