# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from models.db_model import (
    Chat,
    ConsultaUsuario,
    FeedbackResposta,
    IntencaoConsulta,
    RespostaSistema,
)
from api.utils.exceptions import NLPProcessingError, DatabaseConnectionError, DataNotFoundError
from nlp_processor import orchestrator

logger = logging.getLogger(__name__)

_HISTORICO_MAX_TURNOS = 10


def _features_to_geojson(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _bbox_to_wkt(bbox: list[float]) -> WKTElement:
    minx, miny, maxx, maxy = bbox
    wkt = (
        f"POLYGON(({minx} {miny}, {maxx} {miny}, "
        f"{maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
    )
    return WKTElement(wkt, srid=4326)


def _compute_bbox(features: list[dict]) -> Optional[list[float]]:
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
    session: AsyncSession,
    chat_id: Optional[UUID],
    usuario_id: Optional[UUID] = None,
) -> Chat:
    if chat_id:
        result = await session.get(Chat, chat_id)
        if result:
            return result

    chat = Chat(usuario_id=usuario_id)
    session.add(chat)
    await session.flush()
    return chat


async def _load_historico(session: AsyncSession, chat_id: UUID) -> list[dict]:
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
        .limit(_HISTORICO_MAX_TURNOS)
    )
    rows = list(reversed((await session.execute(stmt)).all()))

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
            mensagem = {
                "role": "assistant",
                "content": resposta.texto_resposta,
                "intencao": consulta.intencao_detectada,
                "data_hora": consulta.data_hora,
            }
            if feedback_avaliacao is not None:
                mensagem["feedback"] = int(feedback_avaliacao)
            historico.append(mensagem)

    return historico


async def _next_turno(session: AsyncSession, chat_id: UUID) -> int:
    stmt = select(func.coalesce(func.max(ConsultaUsuario.turno), 0)).where(
        ConsultaUsuario.chat_id == chat_id
    )
    return (await session.execute(stmt)).scalar() + 1


async def _get_or_create_intencao(session: AsyncSession, nome: str) -> IntencaoConsulta:
    stmt = select(IntencaoConsulta).where(IntencaoConsulta.nome == nome).limit(1)
    intencao = (await session.execute(stmt)).scalar_one_or_none()
    if intencao is not None:
        return intencao

    intencao = IntencaoConsulta(nome=nome)
    session.add(intencao)
    await session.flush()
    return intencao


class NLPProcessor:
    async def process(
        self,
        session: AsyncSession,
        pergunta: str,
        chat_id: Optional[UUID] = None,
        municipio: Optional[str] = None,
        usuario_id: Optional[UUID] = None,
    ) -> dict:
        chat = await _load_or_create_chat(session, chat_id, usuario_id=usuario_id)
        historico = await _load_historico(session, chat.id)

        try:
            nlp_result = await orchestrator.run(
                session=session,
                pergunta=pergunta,
                historico=historico,
                municipio_contexto=municipio,
            )
            texto = nlp_result.texto
            features = nlp_result.features
            fontes = [f.model_dump() for f in nlp_result.fontes]
            status = nlp_result.status

            if status == "erro":
                raise NLPProcessingError("Erro interno no pipeline NLP.")

        except SQLAlchemyError as e:
            logger.exception("Erro de banco de dados no pipeline NLP")
            raise DatabaseConnectionError("Erro de acesso ao banco de dados.") from e
        except (NLPProcessingError, DataNotFoundError):
            raise
        except Exception as e:
            logger.exception("Erro crítico no pipeline NLP")
            raise NLPProcessingError("Erro ao processar pergunta pelo NLP.") from e

        turno = await _next_turno(session, chat.id)

        intencao_nome = nlp_result.intencao or status
        intencao_obj = await _get_or_create_intencao(session, intencao_nome)

        consulta = ConsultaUsuario(
            chat_id=chat.id,
            pergunta=pergunta,
            data_hora=datetime.utcnow(),
            intencao_detectada=intencao_nome,
            entidades_detectadas_json=None,
            filtros_detectados_json=None,
            intencao_id=intencao_obj.id,
            intencao_score=nlp_result.confianca,
            turno=turno,
        )
        session.add(consulta)
        await session.flush()

        bbox = nlp_result.bbox or _compute_bbox(features)
        mapa = _features_to_geojson(features)

        resposta = RespostaSistema(
            consulta_usuario_id=consulta.id,
            texto_resposta=texto,
            sql_executado=nlp_result.sql_executado,
            fontes_utilizadas_json={"fontes": fontes},
            bbox_resultado=_bbox_to_wkt(bbox) if bbox else None,
            mapa_geojson=mapa,
            tempo_resposta_ms=nlp_result.tempo_ms,
            mensagem_erro=None,
            status=status,
        )
        session.add(resposta)
        await session.flush()

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
            "confianca": nlp_result.confianca,
            "confianca_faixa": nlp_result.confianca_faixa,
        }
