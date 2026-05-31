# -*- coding: utf-8 -*-
"""
Processador principal NLP — orquestra carregamento do histórico,
execução do agente e persistência dos resultados no banco.
"""
from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Optional
from uuid import UUID

from geoalchemy2.elements import WKTElement

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_model import (
    Chat,
    ConsultaUsuario,
    FeedbackResposta,
    IntencaoConsulta,
    RespostaSistema,
)
from api.utils.exceptions import NLPProcessingError, DatabaseConnectionError, DataNotFoundError
from sqlalchemy.exc import SQLAlchemyError
from nlp_processor.agent import run_agent

logger = logging.getLogger(__name__)

# Número de turnos de histórico enviados ao agente (limitado para economizar tokens)
HISTORICO_MAX_TURNOS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _features_to_geojson(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _bbox_to_wkt(bbox: list[float]) -> WKTElement:
    """Converte [minx, miny, maxx, maxy] em WKTElement POLYGON (srid=4326)."""
    minx, miny, maxx, maxy = bbox
    wkt = (
        f"POLYGON(({minx} {miny}, {maxx} {miny}, "
        f"{maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
    )
    return WKTElement(wkt, srid=4326)


def _compute_bbox(features: list[dict]) -> Optional[list[float]]:
    """Calcula bounding box a partir de todas as features coletadas."""
    coords: list[tuple[float, float]] = []

    def _extract(geom: dict) -> None:
        t = geom.get("type", "")
        c = geom.get("coordinates")
        if c is None:
            return
        if t == "Point":
            coords.append((c[0], c[1]))
        elif t in ("LineString", "MultiPoint"):
            coords.extend((p[0], p[1]) for p in c)
        elif t in ("Polygon", "MultiLineString"):
            for ring in c:
                coords.extend((p[0], p[1]) for p in ring)
        elif t == "MultiPolygon":
            for poly in c:
                for ring in poly:
                    coords.extend((p[0], p[1]) for p in ring)

    for f in features:
        if f.get("geometry"):
            _extract(f["geometry"])

    if not coords:
        return None
    xs, ys = zip(*coords)
    return [min(xs), min(ys), max(xs), max(ys)]


async def _load_or_create_chat(
    session: AsyncSession, chat_id: Optional[UUID]
) -> Chat:
    if chat_id:
        result = await session.get(Chat, chat_id)
        if result:
            return result

    chat = Chat()
    session.add(chat)
    await session.flush()
    return chat


async def _load_historico(
    session: AsyncSession, chat_id: UUID
) -> list[dict]:
    """Carrega os últimos N turnos de um chat como mensagens OpenAI.

    Cada mensagem do assistente recebe metadados do turno (`intencao`,
    `data_hora`, `feedback`) — usados pelo agente para decidir se sinais
    de turnos passados ainda são válidos no contexto atual.
    """
    latest_feedback = (
        select(FeedbackResposta.avaliacao)
        .where(FeedbackResposta.resposta_sistema_id == RespostaSistema.id)
        .order_by(FeedbackResposta.data_hora.desc())
        .limit(1)
        .scalar_subquery()
    )

    stmt = (
        select(
            ConsultaUsuario,
            RespostaSistema,
            latest_feedback.label("feedback_avaliacao"),
        )
        .join(
            RespostaSistema,
            RespostaSistema.consulta_usuario_id == ConsultaUsuario.id,
            isouter=True,
        )
        .where(ConsultaUsuario.chat_id == chat_id)
        .order_by(ConsultaUsuario.turno.desc())
        .limit(HISTORICO_MAX_TURNOS)
    )
    rows = (await session.execute(stmt)).all()
    rows = list(reversed(rows))  # ordem cronológica

    historico: list[dict] = []
    for consulta, resposta, feedback_avaliacao in rows:
        if consulta.pergunta:
            historico.append({
                "role": "user",
                "content": consulta.pergunta,
                "intencao": consulta.intencao_detectada,
                "data_hora": consulta.data_hora,
            })
        if resposta and resposta.texto_resposta:
            mensagem_assistente = {
                "role": "assistant",
                "content": resposta.texto_resposta,
                "intencao": consulta.intencao_detectada,
                "data_hora": consulta.data_hora,
            }
            if feedback_avaliacao is not None:
                mensagem_assistente["feedback"] = int(feedback_avaliacao)
            historico.append(mensagem_assistente)
    return historico


async def _next_turno(session: AsyncSession, chat_id: UUID) -> int:
    stmt = select(func.coalesce(func.max(ConsultaUsuario.turno), 0)).where(
        ConsultaUsuario.chat_id == chat_id
    )
    result = await session.execute(stmt)
    return (result.scalar() or 0) + 1


async def _get_or_create_intencao(session: AsyncSession, nome: str) -> IntencaoConsulta:
    stmt = select(IntencaoConsulta).where(IntencaoConsulta.nome == nome).limit(1)
    result = await session.execute(stmt)
    intencao = result.scalar_one_or_none()
    if intencao is not None:
        return intencao

    intencao = IntencaoConsulta(nome=nome)
    session.add(intencao)
    await session.flush()
    return intencao


# ---------------------------------------------------------------------------
# Processador principal
# ---------------------------------------------------------------------------

class NLPProcessor:
    """Ponto de entrada para processar uma mensagem do usuário."""

    async def process(
        self,
        session: AsyncSession,
        pergunta: str,
        chat_id: Optional[UUID] = None,
        municipio: Optional[str] = None,
    ) -> dict:
        """
        Processa uma pergunta e retorna a resposta estruturada para o frontend.

        Retorno:
        {
            "chat_id": UUID,
            "consulta_id": UUID,
            "resposta_id": UUID,
            "texto_resposta": str,
            "fontes_citadas": list[dict],
            "mapa": FeatureCollection (GeoJSON),
            "bbox": [minx, miny, maxx, maxy] | None,
            "status": str,
        }
        """
        inicio_processamento = perf_counter()
        # 1. Obter/criar chat
        chat = await _load_or_create_chat(session, chat_id)

        # 2. Carregar histórico
        historico = await _load_historico(session, chat.id)

        # 3. Executar agente
        try:
            resultado = await run_agent(
                session=session,
                pergunta=pergunta,
                historico=historico,
                municipio=municipio,
            )
            texto = resultado.get("texto_resposta", "")
            features = resultado.get("features", [])
            fontes = resultado.get("fontes", [])
            status = resultado.get("status", "erro")
            
            # Se o agente indicou erro explicitamente sem lançar exception, lançamos para ativar o Fallback
            if status == "erro":
                raise NLPProcessingError(resultado.get("mensagem_erro", "Erro desconhecido no NLP"))
            elif status == "sem_resultado":
                raise DataNotFoundError("Dados não encontrados para a consulta.")

        except SQLAlchemyError as e:
            logger.exception("Erro de banco de dados na execução do agente")
            raise DatabaseConnectionError("Erro de acesso ou timeout no banco de dados.") from e
        except (NLPProcessingError, DataNotFoundError):
            raise
        except Exception as e:
            logger.exception("Erro crítico no agente NLP")
            raise NLPProcessingError("Ocorreu um erro excecional ao processar sua pergunta pelo NLP.") from e

        # 4. Calcular turno
        turno = await _next_turno(session, chat.id)

        # 5. Garantir intenção no catálogo e salvar consulta do usuário
        intencao_nome = resultado.get("intencao")
        intencao_obj = None
        if intencao_nome:
            intencao_obj = await _get_or_create_intencao(session, intencao_nome)

        # 6. Salvar consulta do usuário
        consulta = ConsultaUsuario(
            chat_id=chat.id,
            pergunta=pergunta,
            data_hora=datetime.utcnow(),
            intencao_detectada=intencao_nome,
            entidades_detectadas_json=resultado.get("entidades_detectadas_json"),
            filtros_detectados_json=resultado.get("filtros_detectados_json"),
            intencao_id=intencao_obj.id if intencao_obj else None,
            intencao_score=resultado.get("intencao_score"),
            turno=turno,
        )
        session.add(consulta)
        await session.flush()

        # 7. Calcular bbox. Algumas ferramentas retornam um bbox de foco
        # (ex.: polígono do imóvel consultado) mesmo quando o mapa inclui
        # passivos próximos que não devem deslocar a câmera principal.
        bbox = resultado.get("bbox") or _compute_bbox(features)

        # 8. Montar GeoJSON da resposta
        mapa = _features_to_geojson(features)

        # 9. Persistir resposta
        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta=texto,
            sql_executado=resultado.get("sql_executado"),
            fontes_utilizadas_json={"fontes": fontes},
            bbox_resultado=_bbox_to_wkt(bbox) if bbox else None,
            mapa_geojson=mapa,
            tempo_resposta_ms=resultado.get("tempo_resposta_ms"),
            mensagem_erro=resultado.get("mensagem_erro"),
            status=status,
        )
        session.add(resposta)
        await session.flush()

        # 9. Atualizar título do chat (primeiro turno)
        if turno == 1 and not chat.title:
            chat.title = pergunta[:120]
            await session.flush()

        await session.commit()

        return {
            "chat_id": chat.id,
            "consulta_id": consulta.id,
            "resposta_id": resposta.id,
            "texto_resposta": texto,
            "fontes_citadas": fontes,
            "mapa": mapa,
            "bbox": bbox,
            "status": status,
        }
