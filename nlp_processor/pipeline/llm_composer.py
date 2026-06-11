# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from nlp_processor.domain.contracts import ToolResult
from nlp_processor.domain.enums import Operacao
from nlp_processor.infrastructure.llm_client import completar

logger = logging.getLogger(__name__)

_SISTEMA = (
    "Você reescreve um resumo factual de dados ambientais do estado de São Paulo "
    "em um texto fluente e claro em português do Brasil. Use EXCLUSIVAMENTE os "
    "números, nomes e fatos do resumo fornecido. NUNCA invente, estime ou acrescente "
    "dados. Seja conciso, direto e não use markdown."
)


def deve_compor(resultados: list[ToolResult]) -> bool:
    if not any(r.total > 0 for r in resultados):
        return False
    if len(resultados) > 1:
        return True
    return any(
        r.operacao in (Operacao.PASSIVOS, Operacao.SOBREPOR) or r.spec.contexto_espacial
        for r in resultados
    )


async def compor(pergunta: str, texto_factual: str) -> str | None:
    mensagens = [
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nResumo factual:\n{texto_factual}"},
    ]
    texto = await completar(mensagens, temperatura=0.2)
    return texto.strip() if texto else None
