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
    "buscar_quilombolas": "buscar_territorios_quilombolas",
    "buscar_imoveis_rurais": "buscar_imoveis_rurais",
    "buscar_imoveis_queimada": "buscar_imoveis_por_queimada",
    "buscar_imoveis_desmatamento": "buscar_imoveis_por_desmatamento",
    "buscar_imoveis_ti": "buscar_imoveis_por_terra_indigena",
    "buscar_imoveis_quilombo": "buscar_imoveis_por_quilombo",
    "buscar_camadas_estaduais": "buscar_camadas_estaduais",
    "buscar_imoveis_em_camadas": "buscar_imoveis_com_camadas_estaduais",
    "buscar_passivos_imovel": "buscar_passivos_em_imovel",
    "buscar_focos_queimada_imovel": "buscar_focos_queimada_imovel",
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
        if ent.codigo_car:
            base["codigo_car"] = ent.codigo_car

    elif intencao == "buscar_camadas_estaduais":
        # Utiliza tema como filtro se disponível
        pass

    elif intencao == "buscar_imoveis_em_camadas":
        # Utiliza tema como filtro se disponível
        pass

    elif intencao == "buscar_passivos_imovel":
        # Se o extrator capturou um código CAR, envia-o como argumento
        if hasattr(ent, "codigo_car") and ent.codigo_car:
            base["codigo_car"] = ent.codigo_car

    elif intencao == "buscar_focos_queimada_imovel":
        if ent.codigo_car:
            base["codigo_car"] = ent.codigo_car
        if ent.data_inicio:
            base["data_inicio"] = ent.data_inicio
        if ent.data_fim:
            base["data_fim"] = ent.data_fim

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
    sql_partes: list[str] = []
    mensagens_erro: list[str] = []
    bbox = None

    # --- consulta geoespacial ---
    tool_name = _INTENT_MAP.get(intencao)
    if tool_name:
        fn = TOOL_FUNCTIONS.get(tool_name)
        if fn:
            args = _build_args(intencao, entidades)
            try:
                result = await fn(session, **args)
                features.extend(result.get("features", []))
                if result.get("bbox"):
                    bbox = result["bbox"]
                for f in result.get("fontes", []):
                    fontes[f["nome"]] = f
                descricao_partes.append(result.get("descricao", ""))
                if result.get("sql_executado"):
                    sql_partes.append(result["sql_executado"])
            except Exception:
                logger.exception("Erro ao executar ferramenta '%s'", tool_name)
                mensagens_erro.append(f"Erro ao executar ferramenta '{tool_name}'.")

    # --- consulta RAG em documentos ---
    if query_embedding:
        try:
            rag_result = await buscar_documentos_rag(session, query_embedding, limite=4)
            contexto_documental = rag_result.get("contexto_textual", "")
            for f in rag_result.get("fontes", []):
                fontes[f["nome"]] = f
            if rag_result.get("sql_executado"):
                sql_partes.append(rag_result["sql_executado"])
        except Exception:
            logger.exception("Erro na busca RAG")
            mensagens_erro.append("Erro na busca RAG.")

    return {
        "features": features,
        "bbox": bbox,
        "fontes": list(fontes.values()),
        "descricao": " ".join(descricao_partes),
        "contexto_documental": contexto_documental,
        "sql_executado": "\n\n".join(sql_partes) if sql_partes else None,
        "mensagem_erro": " ".join(mensagens_erro) if mensagens_erro else None,
    }
