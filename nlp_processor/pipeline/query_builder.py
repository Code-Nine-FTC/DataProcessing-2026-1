# -*- coding: utf-8 -*-
"""
Mapeia (intenção, entidades) para chamadas às ferramentas do banco de dados
e retorna os resultados consolidados.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.entity_extractor import Entidades
from nlp_processor.tools import (
    TOOL_FUNCTIONS,
    buscar_documentos_rag,
)

logger = logging.getLogger(__name__)

# Intenções que produzem dados geoespaciais
_INTENT_MAP: dict[str, str] = {
    "buscar_queimadas": "buscar_queimadas",
    "buscar_desmatamentos": "buscar_desmatamentos",
    "buscar_unidades_conservacao": "buscar_unidades_conservacao",
    "buscar_terras_indigenas": "buscar_terras_indigenas",
    "buscar_assentamentos": "buscar_assentamentos",
    "buscar_quilombolas": "buscar_territorios_quilombolas",
    "buscar_imoveis_rurais": "buscar_imoveis_rurais",
}


def _build_args(intencao: str, ent: Entidades) -> dict[str, Any]:
    """Constrói os kwargs para a função de consulta a partir das entidades."""
    base: dict[str, Any] = {}

    if ent.municipio:
        base["municipio"] = ent.municipio

    if intencao == "buscar_queimadas":
        if ent.data_inicio:
            base["data_inicio"] = ent.data_inicio
        if ent.data_fim:
            base["data_fim"] = ent.data_fim

    elif intencao == "buscar_desmatamentos":
        if ent.data_inicio:
            base["data_inicio"] = ent.data_inicio
        if ent.data_fim:
            base["data_fim"] = ent.data_fim

    elif intencao == "buscar_unidades_conservacao":
        if ent.categoria_uc:
            base["categoria"] = ent.categoria_uc
        if ent.grupo_snuc:
            base["grupo_snuc"] = ent.grupo_snuc

    elif intencao == "buscar_terras_indigenas":
        if ent.fase_ti:
            base["fase"] = ent.fase_ti

    elif intencao == "buscar_assentamentos":
        pass  # nenhum filtro extra por ora

    elif intencao == "buscar_quilombolas":
        pass

    elif intencao == "buscar_imoveis_rurais":
        pass

    return base


async def executar_consulta(
    session: AsyncSession,
    intencao: str,
    entidades: Entidades,
    query_embedding: list[float],
) -> dict:
    """
    Executa a consulta no banco de acordo com a intenção e entidades detectadas.

    Retorna dict com:
        features, fontes, descricao, contexto_documental, bbox
    """
    features: list[dict] = []
    fontes: dict[str, dict] = {}
    descricao_partes: list[str] = []
    contexto_documental = ""

    # --- consulta geoespacial ---
    tool_name = _INTENT_MAP.get(intencao)
    if tool_name:
        fn = TOOL_FUNCTIONS.get(tool_name)
        if fn:
            args = _build_args(intencao, entidades)
            try:
                result = await fn(session, **args)
                features.extend(result.get("features", []))
                for f in result.get("fontes", []):
                    fontes[f["nome"]] = f
                descricao_partes.append(result.get("descricao", ""))
            except Exception:
                logger.exception("Erro ao executar ferramenta '%s'", tool_name)

    # --- consulta RAG em documentos ---
    if query_embedding:
        try:
            rag_result = await buscar_documentos_rag(session, query_embedding, limite=4)
            contexto_documental = rag_result.get("contexto_textual", "")
            for f in rag_result.get("fontes", []):
                fontes[f["nome"]] = f
        except Exception:
            logger.exception("Erro na busca RAG")

    return {
        "features": features,
        "fontes": list(fontes.values()),
        "descricao": " ".join(descricao_partes),
        "contexto_documental": contexto_documental,
    }
