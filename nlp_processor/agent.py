# -*- coding: utf-8 -*-
"""
Orquestrador do pipeline NLP local — sem dependências de LLMs externos.

Fluxo:
  1. Pré-processa o texto
  2. Classifica a intenção (TF-IDF + Logistic Regression)
  3. Extrai entidades (regex + gazetteer)
  4. Gera embedding da pergunta (sentence-transformers, para RAG)
  5. Executa consulta(s) no banco via query_builder
  6. Formata a resposta textual com citação de fontes
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.intent_classifier import get_classifier
from nlp_processor.pipeline.entity_extractor import extrair_entidades
from nlp_processor.pipeline.embedder import get_embedder
from nlp_processor.pipeline.query_builder import executar_consulta
from nlp_processor.pipeline.response_formatter import formatar_resposta

logger = logging.getLogger(__name__)

# Limiar mínimo de confiança para aceitar a intenção detectada.
# Abaixo disso, cai para buscar_documentos (mais genérico).
# Com 9 classes, probabilidades acima de 0.35 já indicam predição confiável.
CONFIDENCE_THRESHOLD = 0.35


async def run_agent(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict],  # mantido para compatibilidade com index.py
) -> tuple[str, list[dict], list[dict], str]:
    """
    Executa o pipeline NLP local.

    Retorna:
        (texto_resposta, features_geojson, fontes, status)
        status: 'sucesso' | 'sem_resultado' | 'fora_escopo' | 'erro'
    """
    classifier = get_classifier()
    embedder = get_embedder()

    # 1. Classificação de intenção
    if not classifier.is_ready():
        logger.error("Modelo de intenções não treinado. Execute nlp_processor.training.train")
        return (
            "O sistema de processamento de linguagem não está treinado. "
            "Execute `python -m nlp_processor.training.train` antes de usar o chat.",
            [],
            [],
            "erro",
        )

    intencao, confianca = classifier.predict(pergunta)
    logger.info("Intenção detectada: %s (%.2f)", intencao, confianca)

    if confianca < CONFIDENCE_THRESHOLD:
        intencao = "buscar_documentos"
        logger.info("Confiança baixa — usando buscar_documentos como fallback.")

    # 2. Extração de entidades
    entidades = extrair_entidades(pergunta)

    # 3. Embedding para RAG
    query_embedding: list[float] = []
    try:
        query_embedding = embedder.embed(pergunta)
    except Exception:
        logger.warning("Não foi possível gerar embedding — RAG desativado.")

    # 4. Consulta ao banco
    try:
        resultado = await executar_consulta(
            session=session,
            intencao=intencao,
            entidades=entidades,
            query_embedding=query_embedding,
        )
    except Exception:
        logger.exception("Erro ao executar consulta no banco.")
        return (
            "Ocorreu um erro ao consultar os dados. Tente novamente.",
            [],
            [],
            "erro",
        )

    features = resultado["features"]
    fontes = resultado["fontes"]
    contexto_documental = resultado["contexto_documental"]

    # 5. Determinar status
    if intencao == "fora_escopo":
        status = "fora_escopo"
    elif not features and not contexto_documental:
        status = "sem_resultado"
    else:
        status = "sucesso"

    # 6. Formatar resposta
    texto = formatar_resposta(
        intencao=intencao,
        entidades=entidades,
        total_features=len(features),
        fontes=fontes,
        contexto_documental=contexto_documental,
        confianca=confianca,
    )

    return texto, features, fontes, status

