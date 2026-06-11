# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_model import Documento, DocumentoTrecho
from nlp_processor.infrastructure.embedder import embed_texto

logger = logging.getLogger(__name__)

_RELEVANCIA_MINIMA = 0.30
_LIMITE_TRECHOS = 5


async def buscar_trechos(
    session: AsyncSession,
    pergunta: str,
    limite: int = _LIMITE_TRECHOS,
) -> list[dict]:
    embedding = embed_texto(pergunta).tolist()

    stmt = (
        select(
            DocumentoTrecho.texto,
            DocumentoTrecho.documento_id,
            Documento.titulo if hasattr(Documento, "titulo") else DocumentoTrecho.documento_id,
            (1 - DocumentoTrecho.embedding.cosine_distance(embedding)).label("relevancia"),
        )
        .join(Documento, DocumentoTrecho.documento_id == Documento.id, isouter=True)
        .where(
            (1 - DocumentoTrecho.embedding.cosine_distance(embedding)) >= _RELEVANCIA_MINIMA
        )
        .order_by((1 - DocumentoTrecho.embedding.cosine_distance(embedding)).desc())
        .limit(limite)
    )

    try:
        rows = (await session.execute(stmt)).all()
    except Exception as exc:
        logger.warning("Erro na busca RAG: %s", exc)
        return []

    return [
        {
            "texto": row.texto,
            "relevancia": float(row.relevancia),
        }
        for row in rows
    ]
