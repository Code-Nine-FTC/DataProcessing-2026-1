# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from time import perf_counter
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.domain.contracts import RespostaNLP
from nlp_processor.engine import query_engine
from nlp_processor.infrastructure import gazetteer, llm_client
from nlp_processor.pipeline import (
    entity_extractor,
    llm_composer,
    llm_fallback,
    responder,
    semantic_router,
    text_hygiene,
)

logger = logging.getLogger(__name__)


def _ms(inicio: float) -> int:
    return int((perf_counter() - inicio) * 1000)


async def warm_up(session: AsyncSession) -> None:
    await gazetteer.warm_up(session)
    text_hygiene.registrar_nomes_proprios(gazetteer.vocabulario_tokens())
    await semantic_router.warm_up()


async def run(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict] | None = None,
    municipio_contexto: Optional[str] = None,
) -> RespostaNLP:
    inicio = perf_counter()

    if not gazetteer.is_ready():
        await warm_up(session)

    texto = text_hygiene.processar(pergunta)

    plano = await semantic_router.entender(texto)

    if plano.fora_escopo:
        resultado = await llm_fallback.responder(pergunta, historico, motivo="fora_escopo")
        return resultado.model_copy(update={"tempo_ms": _ms(inicio)})

    if plano.confianca < semantic_router.CONFIDENCE_THRESHOLD or not plano.specs:
        resultado = await llm_fallback.responder(pergunta, historico, motivo="baixa_confianca")
        return resultado.model_copy(update={"tempo_ms": _ms(inicio)})

    specs = await entity_extractor.extrair_e_validar(session, plano, texto, municipio_contexto)

    resultados = await query_engine.executar(session, specs)

    resposta = responder.compor(resultados, plano.confianca)

    if llm_client.disponivel() and llm_composer.deve_compor(resultados):
        texto_llm = await llm_composer.compor(pergunta, resposta.texto)
        if texto_llm:
            resposta = resposta.model_copy(update={"texto": texto_llm})

    return resposta.model_copy(update={"tempo_ms": _ms(inicio)})
