# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from nlp_processor.domain.contracts import RespostaNLP
from nlp_processor.infrastructure.llm_client import completar

logger = logging.getLogger(__name__)

_SISTEMA_PROMPT = (
    "Você é um assistente especializado em análises geográficas e ambientais "
    "do estado de São Paulo. Você tem acesso a dados sobre: focos de queimada, "
    "alertas de desmatamento, unidades de conservação, terras indígenas, "
    "territórios quilombolas, assentamentos rurais e imóveis rurais (CAR/SICAR). "
    "Você NÃO tem acesso a dados de outros estados. "
    "Se a pergunta estiver fora do seu escopo, explique educadamente o que "
    "você pode responder e sugira como reformular a pergunta."
)

_TEXTO_PADRAO = (
    "Esta pergunta está fora do escopo do sistema ou não foi compreendida. "
    "O assistente é especializado em análises geográficas e ambientais "
    "do estado de São Paulo."
)


async def responder(
    pergunta: str,
    historico: list[dict] | None = None,
    motivo: str = "baixa_confianca",
) -> RespostaNLP:
    mensagens: list[dict] = [{"role": "system", "content": _SISTEMA_PROMPT}]

    if historico:
        for msg in historico[-4:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                mensagens.append({"role": role, "content": content})

    mensagens.append({"role": "user", "content": pergunta})

    logger.info("Fallback LLM acionado (motivo=%s): %s", motivo, pergunta[:80])
    texto = await completar(mensagens) or _TEXTO_PADRAO

    status = "fora_escopo" if motivo == "fora_escopo" else "fallback"
    return RespostaNLP(
        texto=texto,
        features=[],
        bbox=None,
        fontes=[],
        status=status,
        confianca=0.0,
    )
