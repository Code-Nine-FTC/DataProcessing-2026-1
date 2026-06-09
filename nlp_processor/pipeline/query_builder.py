# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.entity_extractor import Entidades
from nlp_processor.tools import (
    TOOL_FUNCTIONS,
    buscar_documentos_rag,
)

logger = logging.getLogger(__name__)

INTENT_TO_TOOL_MAP: Dict[str, str] = {
    "buscar_queimadas": "buscar_queimadas",
    "buscar_desmatamentos": "buscar_desmatamentos",
    "buscar_unidades_conservacao": "buscar_unidades_conservacao",
    "buscar_terras_indigenas": "buscar_terras_indigenas",
    "buscar_assentamentos": "buscar_assentamentos",
    "buscar_quilombolas": "buscar_territorios_quilombolas",
    "buscar_imoveis_rurais": "buscar_imoveis_rurais",
    "buscar_imoveis_queimada": "buscar_imoveis_por_queimada",
    "buscar_imoveis_desmatamento": "buscar_imoveis_por_desmatamento",
    "buscar_imoveis_quilombo": "buscar_imoveis_por_quilombo",
    "buscar_imoveis_ti": "buscar_imoveis_por_terra_indigena",
    "buscar_camadas_estaduais": "buscar_camadas_estaduais",
    "buscar_imoveis_em_camadas": "buscar_imoveis_com_camadas_estaduais",
    "buscar_passivos_imovel": "buscar_passivos_em_imovel",
    "buscar_focos_queimada_imovel": "buscar_focos_queimada_imovel",
    "buscar_documentos": "buscar_documentos_rag",
    "buscar_maiores_quantidades": "buscar_maiores_quantidades",
    "buscar_queimadas_em_quilombolas": "buscar_queimadas_em_quilombolas",
}

_ABSORBED_BY_MAIORES_QUANTIDADES: Set[str] = {
    "buscar_queimadas",
    "buscar_desmatamentos",
    "buscar_terras_indigenas",
    "buscar_unidades_conservacao",
    "buscar_quilombolas",
}

CAR_SCOPED_INTENTS: Set[str] = {
    "buscar_imoveis_rurais",
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
}

RA_EXCLUDED_INTENTS: Set[str] = {
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
}


def _build_base_arguments(intent: str, entities: Entidades) -> Dict[str, Any]:
    arguments: Dict[str, Any] = {}
    has_car = bool(entities.codigo_car)
    is_car_intent = intent in CAR_SCOPED_INTENTS

    if entities.municipio and not (has_car and is_car_intent):
        arguments["municipio"] = entities.municipio

    if (
        entities.regiao_administrativa
        and not entities.municipio
        and intent not in RA_EXCLUDED_INTENTS
        and not (has_car and is_car_intent)
    ):
        arguments["regiao_administrativa"] = entities.regiao_administrativa

    return arguments


def _extract_intent_specific_arguments(intent: str, entities: Entidades) -> Dict[str, Any]:
    specific_args: Dict[str, Any] = {}
    
    mapping_config = {
        "data_inicio": ["buscar_queimadas", "buscar_desmatamentos", "buscar_focos_queimada_imovel"],
        "data_fim": ["buscar_queimadas", "buscar_desmatamentos", "buscar_focos_queimada_imovel"],
        "codigo_car": ["buscar_imoveis_rurais", "buscar_passivos_imovel", "buscar_focos_queimada_imovel"],
        "categoria_uc": ["buscar_unidades_conservacao"],
        "grupo_snuc": ["buscar_unidades_conservacao"],
        "fase_ti": ["buscar_terras_indigenas"],
        "tipo_alerta": ["buscar_desmatamentos"],
        "esfera_uc": ["buscar_unidades_conservacao"],
        "bioma": ["buscar_queimadas", "buscar_queimadas_em_quilombolas", "buscar_maiores_quantidades"],
    }

    alias_config = {
        "categoria_uc": "categoria",
        "fase_ti": "fase",
        "esfera_uc": "esfera",
    }

    for entity_attr, valid_intents in mapping_config.items():
        if intent in valid_intents and hasattr(entities, entity_attr):
            value = getattr(entities, entity_attr)
            if value:
                arg_name = alias_config.get(entity_attr, entity_attr)
                specific_args[arg_name] = value

    return specific_args


def build_tool_arguments(intent: str, entities: Entidades) -> Dict[str, Any]:
    arguments = _build_base_arguments(intent, entities)
    specific_arguments = _extract_intent_specific_arguments(intent, entities)
    arguments.update(specific_arguments)
    return arguments


async def executar_consulta(
    session: AsyncSession,
    intents: List[Tuple[str, float]],
    entities: Entidades,
    query_embedding: Optional[List[float]],
) -> Dict[str, Any]:
    features: List[Dict[str, Any]] = []
    sources: Dict[str, Dict[str, Any]] = {}
    per_intent: Dict[str, Dict[str, Any]] = {}
    sql_segments: List[str] = []
    error_messages: List[str] = []
    bbox = None
    document_context = ""

    maiores_quantidades_presente = any(i == "buscar_maiores_quantidades" for i, _ in intents)

    for intent, confidence in intents:
        if intent == "fora_escopo":
            continue

        if maiores_quantidades_presente and intent in _ABSORBED_BY_MAIORES_QUANTIDADES:
            continue

        if intent == "buscar_passivos_imovel" and not entities.codigo_car:
            logger.info("Intenção 'buscar_passivos_imovel' ignorada: nenhum código CAR detectado.")
            continue

        tool_name = INTENT_TO_TOOL_MAP.get(intent)
        if not tool_name:
            continue

        tool_function = TOOL_FUNCTIONS.get(tool_name)
        if not tool_function:
            continue

        tool_args = build_tool_arguments(intent, entities)

        if intent == "buscar_maiores_quantidades":
            tool_args["intents"] = intents
            tool_args["limit_dinamico"] = getattr(entities, "limite", 3)
            tool_args["is_ranking"] = getattr(entities, "is_ranking", False)

        try:
            result = await tool_function(session, **tool_args)
            intent_features = result.get("features", [])
            intent_fontes = result.get("fontes", [])

            features.extend(intent_features)

            if result.get("bbox"):
                bbox = result["bbox"]

            for source in intent_fontes:
                sources[source["nome"]] = source

            if result.get("sql_executado"):
                sql_segments.append(result["sql_executado"])

            per_intent[intent] = {
                "total": result.get("total", len(intent_features)),
                "fontes": intent_fontes,
                "descricao": result.get("descricao", ""),
            }

        except Exception:
            logger.exception("Error executing database tool: %s", tool_name)
            error_messages.append(f"Error executing tool '{tool_name}'.")

    if query_embedding:
        try:
            rag_result = await buscar_documentos_rag(session, query_embedding, limite=4)
            document_context = rag_result.get("contexto_textual", "")

            for source in rag_result.get("fontes", []):
                sources[source["nome"]] = source

            if rag_result.get("sql_executado"):
                sql_segments.append(rag_result["sql_executado"])

        except Exception:
            logger.exception("Error during RAG document search execution")
            error_messages.append("Error during RAG search.")

    return {
        "features": features,
        "bbox": bbox,
        "fontes": list(sources.values()),
        "per_intent": per_intent,
        "descricao": " ".join(d["descricao"] for d in per_intent.values() if d.get("descricao")),
        "contexto_documental": document_context,
        "sql_executado": "\n\n".join(sql_segments) if sql_segments else None,
        "mensagem_erro": " ".join(error_messages) if error_messages else None,
    }