# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from datetime import datetime
from time import time
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
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
    FallbackResponse,
    QgisIntegracao,
)
from api.utils.qgis_integracao import montar_integracao_qgis
from api.utils.exceptions import NLPProcessingError, DatabaseConnectionError, DataNotFoundError
from api.utils.fallback_logger import FallbackLogger
from api.utils.fallback_metrics import FallbackMetrics
from models.db_model import Chat, ConsultaUsuario, FeedbackResposta, RespostaSistema, Usuario
from nlp_processor.index import NLPProcessor

logger = logging.getLogger(__name__)

_processor = NLPProcessor()
_fallback_logger = FallbackLogger()
_fallback_metrics = FallbackMetrics()


class ChatService:
    @staticmethod
    def _assert_chat_access(chat: Chat, current_user: Optional[Usuario]) -> None:
        if not chat.ativo:
            raise HTTPException(status_code=404, detail="Chat não encontrado.")
        if chat.usuario_id is None:
            return
        if current_user is None or chat.usuario_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Sem permissão para este chat.",
            )

    async def _prepare_chat_for_message(
        self,
        req: ChatMensagemRequest,
        session: AsyncSession,
        current_user: Optional[Usuario],
    ) -> None:
        if not req.chat_id:
            return

        chat = await session.get(Chat, req.chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat não encontrado.")

        self._assert_chat_access(chat, current_user)

        if chat.usuario_id is None and current_user is not None:
            chat.usuario_id = current_user.id
            await session.flush()

    # ------------------------------------------------------------------
    # Enviar mensagem
    # ------------------------------------------------------------------

    async def enviar_mensagem(
        self,
        req: ChatMensagemRequest,
        session: AsyncSession,
        current_user: Optional[Usuario] = None,
    ) -> ChatMensagemResponse:
        start_time = time()
        try:
            await self._prepare_chat_for_message(req, session, current_user)
            result = await self._process_with_fallback(req, session, current_user)
            return self._build_success_response(result)
            
        except NLPProcessingError as e:
            return await self._handle_nlp_fallback(req, e, start_time)
            
        except DatabaseConnectionError as e:
            return await self._handle_database_fallback(req, e, start_time)
            
        except DataNotFoundError as e:
            return await self._handle_data_fallback(req, e, start_time)
            
        except SQLAlchemyError as e:
            return await self._handle_database_fallback(req, e, start_time)
            
        except Exception as e:
            return await self._handle_generic_fallback(req, e, start_time)

    async def _process_with_fallback(
        self,
        req: ChatMensagemRequest,
        session: AsyncSession,
        current_user: Optional[Usuario] = None,
    ) -> dict:
        usuario_id = current_user.id if current_user else None
        return await _processor.process(
            session=session,
            pergunta=req.pergunta,
            chat_id=req.chat_id,
            municipio=req.municipio,
            usuario_id=usuario_id,
        )

    def _build_success_response(self, result: dict) -> ChatMensagemResponse:
        mapa_raw = result.get("mapa", {"type": "FeatureCollection", "features": []})
        mapa = FeatureCollection(**mapa_raw)

        fontes = [FonteCitada(**f) for f in result.get("fontes_citadas", [])]

        return ChatMensagemResponse(
            chat_id=result["chat_id"],
            consulta_id=result["consulta_id"],
            resposta_id=result["resposta_id"],
            texto_resposta=result["texto_resposta"],
            fontes_citadas=fontes,
            mapa=mapa,
            bbox=result.get("bbox"),
            status=result.get("status", "sucesso"),
            qgis=montar_integracao_qgis(result["resposta_id"]),
            fallback_info=None
        )

    async def _handle_nlp_fallback(self, req: ChatMensagemRequest, e: Exception, start_time: float) -> ChatMensagemResponse:
        tipo = "nlp_fallback"
        mensagem = "Não consegui entender sua pergunta. Tente reformular assim:"
        sugestoes = ["Queimadas em [município]", "Risco ambiental de [propriedade]"]
        return self._build_fallback_response(tipo, req, mensagem, sugestoes, start_time)

    async def _handle_data_fallback(self, req: ChatMensagemRequest, e: Exception, start_time: float) -> ChatMensagemResponse:
        tipo = "data_fallback"
        mensagem = "Desculpe, não encontrei informações sobre este assunto."
        sugestoes = ["Deseja pesquisar sobre outro tema?", "Listar propriedades com risco", "Exibir alertas recentes"]
        return self._build_fallback_response(tipo, req, mensagem, sugestoes, start_time)

    async def _handle_database_fallback(self, req: ChatMensagemRequest, e: Exception, start_time: float) -> ChatMensagemResponse:
        tipo = "connection_fallback"
        mensagem = "Estou com dificuldade de acessar os dados. Poderia tentar novamente em alguns minutos?"
        sugestoes = []
        return self._build_fallback_response(tipo, req, mensagem, sugestoes, start_time)

    async def _handle_generic_fallback(self, req: ChatMensagemRequest, e: Exception, start_time: float) -> ChatMensagemResponse:
        tipo = "generic_fallback"
        mensagem = "Ocorreu um erro inesperado ao processar sua solicitação. Tente novamente mais tarde."
        sugestoes = ["Tentar novamente"]
        return self._build_fallback_response(tipo, req, mensagem, sugestoes, start_time)

    def _build_fallback_response(self, tipo: str, req: ChatMensagemRequest, mensagem: str, sugestoes: list, start_time: float) -> ChatMensagemResponse:
        tempo_resposta = time() - start_time
        
        chat_id_str = str(req.chat_id) if req.chat_id else None
        
        _fallback_logger.log_fallback_event(
            tipo_fallback=tipo,
            pergunta_original=req.pergunta,
            resposta_fallback=mensagem,
            sugestoes_providas=sugestoes,
            tempo_resposta=tempo_resposta,
            chat_id=chat_id_str
        )
        
        _fallback_metrics.registrar_fallback(tipo, tempo_resposta)
        
        fallback_info = FallbackResponse(
            tipo_fallback=tipo,
            mensagem_usuario=mensagem,
            sugestoes=sugestoes,
            retry_count=0,
            timestamp=datetime.now()
        )
        
        consulta_id = uuid.uuid4()
        resposta_id = uuid.uuid4()
        
        # Em fallback de mock, geramos um fallback dummy, sem salvar de fato caso não haja banco.
        return ChatMensagemResponse(
            chat_id=req.chat_id or uuid.uuid4(),
            consulta_id=consulta_id,
            resposta_id=resposta_id,
            texto_resposta=mensagem,
            fontes_citadas=[],
            mapa=FeatureCollection(type="FeatureCollection", features=[]),
            bbox=None,
            status="erro",
            qgis=QgisIntegracao(
                crs="EPSG:4326",
                geojson_url_path=f"/api/chat/resposta/{resposta_id}/geojson",
                como_carregar_no_qgis="N/A (Mensagem de falha)"
            ),
            fallback_info=fallback_info
        )

    # ------------------------------------------------------------------
    # Listar chats
    # ------------------------------------------------------------------

    async def listar_chats(
        self, session: AsyncSession, usuario_id: UUID
    ) -> list[ChatResumo]:
        stmt = (
            select(Chat)
            .where(Chat.ativo == True, Chat.usuario_id == usuario_id)
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
        self,
        chat_id: UUID,
        session: AsyncSession,
        current_user: Optional[Usuario] = None,
    ) -> ChatHistoricoResponse:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat não encontrado.")

        self._assert_chat_access(chat, current_user)

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
        self,
        chat_id: UUID,
        session: AsyncSession,
        current_user: Optional[Usuario] = None,
    ) -> dict:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat não encontrado.")

        self._assert_chat_access(chat, current_user)
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

# ------------------------------------------------------------------
# Gerar Resumo do Relatório 
# ------------------------------------------------------------------

    async def gerar_resumo_relatorio(
        self,
        chat_id: UUID,
        session: AsyncSession,
        current_user: Optional[Usuario] = None,
    ) -> dict:
        try:
            # 1. Pega o histórico completo
            historico = await self.historico_chat(chat_id, session, current_user)
            
            if not historico.mensagens:
                return {
                    "resumo": "Nenhuma conversa encontrada neste chat.",
                    "fontes": []
                }

            resumos_limpos = []
            fontes_acumuladas = []

            for msg in historico.mensagens:
                if msg.resposta:
                    texto_cru = msg.resposta
                    
                    # Limpeza inteligente: Remove metadados brutos que poluem o texto
                    if "Contexto documental:" in texto_cru:
                        texto_cru = texto_cru.split("Contexto documental:")[0]
                    if "Copiar Link QGIS" in texto_cru:
                        texto_cru = texto_cru.split("Copiar Link QGIS")[0]
                    if "📚 Fontes consultadas" in texto_cru:
                        texto_cru = texto_cru.split("📚 Fontes consultadas")[0]
                    
                    texto_limpo = texto_cru.strip()
                    if texto_limpo:
                        resumos_limpos.append(texto_limpo)
                
                # Coleta estruturada das fontes reais salvas no banco
                if msg.fontes:
                    for f in msg.fontes:
                        fonte_dict = {"nome": f.nome, "orgao": getattr(f, 'orgao', ''), "url": getattr(f, 'url', '')}
                        if fonte_dict not in fontes_acumuladas:
                            fontes_acumuladas.append(fonte_dict)

            # Une as principais conclusões encontradas na conversa
            resumo_final = "\n\n".join(resumos_limpos)

            return {
                "resumo": resumo_final,
                "fontes": fontes_acumuladas
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao compilar relatório inteligente: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Erro ao compilar as informações estruturadas do relatório."
            )