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

from dataclasses import asdict
import logging
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.intent_classifier import get_classifier
from nlp_processor.pipeline.entity_extractor import extrair_entidades
from nlp_processor.pipeline.embedder import get_embedder
from nlp_processor.pipeline.preprocessor import normalizar
from nlp_processor.pipeline.query_builder import executar_consulta
from nlp_processor.pipeline.response_formatter import formatar_resposta
from models.db_model import Municipio

logger = logging.getLogger(__name__)

# Limiar mínimo de confiança para aceitar a intenção detectada.
# Abaixo disso, cai para buscar_documentos (mais genérico).
# Com 9 classes, probabilidades acima de 0.35 já indicam predição confiável.
CONFIDENCE_THRESHOLD = 0.35


def _extrair_feedback_contexto(historico: list[dict]) -> dict[str, int]:
    for mensagem in reversed(historico):
        if mensagem.get("role") != "assistant":
            continue

        feedback = mensagem.get("feedback")
        if isinstance(feedback, dict):
            feedback = feedback.get("avaliacao")

        if feedback in (-1, 1):
            return {"avaliacao": int(feedback)}

    return {}


async def _carregar_municipios_normalizados(session: AsyncSession) -> list[str]:
    stmt = select(Municipio.nome).where(Municipio.nome.is_not(None))
    result = await session.execute(stmt)

    nomes: set[str] = set()
    for (nome,) in result.all():
        nomes.add(normalizar(nome))

    logger.info(f"Carregados {len(nomes)} municípios normalizados do banco")
    return sorted(nomes)


def _serializar_entidades(entidades) -> dict[str, Any]:
    return asdict(entidades)


def _serializar_filtros(entidades_json: dict[str, Any]) -> dict[str, Any]:
    return {
        chave: valor
        for chave, valor in entidades_json.items()
        if chave != "palavras_chave" and valor is not None
    }


async def run_agent(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict],  # mantido para compatibilidade com index.py
) -> dict[str, Any]:
    """
    Executa o pipeline NLP local.

    Retorna:
        (texto_resposta, features_geojson, fontes, status)
        status: 'sucesso' | 'sem_resultado' | 'fora_escopo' | 'erro'
    """
    inicio = perf_counter()
    classifier = get_classifier()
    embedder = get_embedder()
    feedback_contexto = _extrair_feedback_contexto(historico)

    def _finalizar(
        texto_resposta: str,
        features: list[dict],
        fontes: list[dict],
        status: str,
        intencao: str | None,
        intencao_score: float | None,
        entidades_detectadas_json: dict[str, Any],
        filtros_detectados_json: dict[str, Any],
        sql_executado: str | None = None,
        mensagem_erro: str | None = None,
    ) -> dict[str, Any]:
        return {
            "texto_resposta": texto_resposta,
            "features": features,
            "fontes": fontes,
            "status": status,
            "intencao": intencao,
            "intencao_score": intencao_score,
            "entidades_detectadas_json": entidades_detectadas_json,
            "filtros_detectados_json": filtros_detectados_json,
            "sql_executado": sql_executado,
            "mensagem_erro": mensagem_erro,
            "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
        }

    # 1. Classificação de intenção
    if not classifier.is_ready():
        logger.error("Modelo de intenções não treinado. Execute nlp_processor.training.train")
        return _finalizar(
            texto_resposta="Ocorreu um erro interno. Tente novamente.",
            features=[],
            fontes=[],
            status="erro",
            intencao=None,
            intencao_score=None,
            entidades_detectadas_json={},
            filtros_detectados_json={},
            mensagem_erro="Modelo de intenções não treinado.",
        )

    intencao, confianca = classifier.predict(pergunta)
    logger.info("Intenção detectada: %s (%.2f)", intencao, confianca)

    # 2. Extração de entidades (fazer ANTES de decidir sobre fallback)
    municipios_extras: list[str] = []
    try:
        municipios_extras = await _carregar_municipios_normalizados(session)
    except Exception:
        logger.warning("Não foi possível carregar municípios do banco; usando gazetteer estático.")

    entidades = extrair_entidades(pergunta, municipios_extras)
    entidades_json = _serializar_entidades(entidades)
    filtros_json = _serializar_filtros(entidades_json)

    # Se confiança é baixa MAS extraímos um município, assume buscar_queimadas
    # (a consulta mais comum é por focos em um local)
    if confianca < CONFIDENCE_THRESHOLD:
        if entidades.municipio:
            intencao = "buscar_queimadas"
            logger.info(
                "Confiança baixa (%.2f) mas município detectado (%s) — "
                "usando buscar_queimadas.",
                confianca,
                entidades.municipio,
            )
        else:
            intencao = "buscar_documentos"
            logger.info("Confiança baixa — usando buscar_documentos como fallback.")

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
        return _finalizar(
            texto_resposta="Ocorreu um erro ao consultar os dados. Tente novamente.",
            features=[],
            fontes=[],
            status="erro",
            intencao=intencao,
            intencao_score=confianca,
            entidades_detectadas_json=entidades_json,
            filtros_detectados_json=filtros_json,
            mensagem_erro="Erro ao executar consulta no banco.",
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
        feedback_contexto=feedback_contexto or None,
    )

    return {
        "texto_resposta": texto,
        "features": features,
        "fontes": fontes,
        "status": status,
        "intencao": intencao,
        "intencao_score": confianca,
        "entidades_detectadas_json": entidades_json,
        "filtros_detectados_json": filtros_json,
        "sql_executado": resultado.get("sql_executado"),
        "mensagem_erro": resultado.get("mensagem_erro"),
        "tempo_resposta_ms": int((perf_counter() - inicio) * 1000),
    }

