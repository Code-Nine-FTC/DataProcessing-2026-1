# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from nlp_processor.domain.contracts import RespostaNLP
from nlp_processor.infrastructure.llm_client import completar

logger = logging.getLogger(__name__)

_ESCOPO = (
    "focos de queimada, alertas de desmatamento, unidades de conservação, terras "
    "indígenas, territórios quilombolas, assentamentos rurais e imóveis rurais "
    "(CAR/SICAR) do estado de São Paulo"
)

_SISTEMA_BASE = (
    "Você é o assistente do sistema de dados geoambientais do estado de São Paulo. "
    f"O sistema responde sobre: {_ESCOPO}. Você NÃO tem acesso a dados de outros "
    "estados nem ao banco de dados. NUNCA invente dados, números, nomes ou "
    "estatísticas. Responda em português do Brasil, de forma curta e educada, sem markdown."
)

_INSTRUCAO = {
    "fora_escopo": (
        "A pergunta está fora do escopo. Explique gentilmente o que o sistema cobre e "
        "sugira como reformular dentro desse escopo."
    ),
    "baixa_confianca": (
        "O sistema não entendeu a pergunta com segurança. Peça uma reformulação mais "
        "específica e dê um exemplo de pergunta que o sistema saberia responder. Não "
        "tente adivinhar números nem responder com dados."
    ),
}

_TEXTO_PADRAO = (
    "Não consegui compreender sua pergunta com segurança. O assistente responde sobre "
    f"{_ESCOPO}. Tente reformular — por exemplo: \"queimadas em Campinas em 2023\"."
)


async def responder(
    pergunta: str,
    historico: list[dict] | None = None,
    motivo: str = "baixa_confianca",
) -> RespostaNLP:
    sistema = f"{_SISTEMA_BASE}\n\n{_INSTRUCAO.get(motivo, _INSTRUCAO['baixa_confianca'])}"
    mensagens: list[dict] = [{"role": "system", "content": sistema}]

    if historico:
        for msg in historico[-4:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                mensagens.append({"role": role, "content": content})

    mensagens.append({"role": "user", "content": pergunta})

    logger.info("Fallback LLM (motivo=%s): %s", motivo, pergunta[:80])
    texto = await completar(mensagens, temperatura=0.2) or _TEXTO_PADRAO

    status = "fora_escopo" if motivo == "fora_escopo" else "fallback"
    return RespostaNLP(
        texto=texto,
        features=[],
        bbox=None,
        fontes=[],
        status=status,
        confianca=0.0,
        confianca_faixa="baixa",
        intencao=motivo,
    )
