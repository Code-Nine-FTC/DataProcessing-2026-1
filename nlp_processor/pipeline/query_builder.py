# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from nlp_processor.pipeline.entity_extractor import Entidades
from nlp_processor.tools import TOOL_FUNCTIONS, buscar_documentos_rag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tabela de despacho 2D: (intent, contexto_espacial) → nome da ferramenta
# ---------------------------------------------------------------------------
# contexto_espacial = None significa "sem restrição espacial" (consulta simples)

DISPATCH: Dict[tuple, str] = {
    # Queimadas
    ("buscar_queimadas", None):                  "buscar_queimadas",
    ("buscar_queimadas", "unidade_conservacao"):  "buscar_queimadas_em_unidades_conservacao",
    ("buscar_queimadas", "terra_indigena"):        "buscar_queimadas_em_terras_indigenas",
    ("buscar_queimadas", "quilombola"):            "buscar_queimadas_em_quilombolas",
    ("buscar_queimadas", "assentamento"):          "buscar_queimadas",  # sem ferramenta específica: usa genérica
    # Desmatamentos
    ("buscar_desmatamentos", None):               "buscar_desmatamentos",
    ("buscar_desmatamentos", "unidade_conservacao"): "buscar_desmatamentos_em_unidades_conservacao",
    ("buscar_desmatamentos", "terra_indigena"):    "buscar_desmatamentos_em_terras_indigenas",
    ("buscar_desmatamentos", "quilombola"):        "buscar_desmatamentos_em_quilombolas",
    ("buscar_desmatamentos", "assentamento"):      "buscar_desmatamentos",
    # Dados territoriais
    ("buscar_unidades_conservacao", None):         "buscar_unidades_conservacao",
    ("buscar_terras_indigenas", None):             "buscar_terras_indigenas",
    ("buscar_assentamentos", None):                "buscar_assentamentos",
    ("buscar_quilombolas", None):                  "buscar_territorios_quilombolas",
    # Imóveis rurais
    ("buscar_imoveis_rurais", None):               "buscar_imoveis_rurais",
    ("buscar_imoveis_queimada", None):             "buscar_imoveis_por_queimada",
    ("buscar_imoveis_desmatamento", None):         "buscar_imoveis_por_desmatamento",
    ("buscar_imoveis_quilombo", None):             "buscar_imoveis_por_quilombo",
    ("buscar_imoveis_ti", None):                   "buscar_imoveis_por_terra_indigena",
    # Camadas e passivos
    ("buscar_camadas_estaduais", None):            "buscar_camadas_estaduais",
    ("buscar_imoveis_em_camadas", None):           "buscar_imoveis_com_camadas_estaduais",
    ("buscar_passivos_imovel", None):              "buscar_passivos_em_imovel",
    ("buscar_focos_queimada_imovel", None):        "buscar_focos_queimada_imovel",
    # Sobreposição entre camadas
    ("buscar_sobreposicao_areas", None):           "buscar_sobreposicao_areas",
    # Ranking
    ("buscar_maiores_quantidades", None):          "buscar_maiores_quantidades",
    ("buscar_maiores_quantidades", "unidade_conservacao"): "buscar_maiores_quantidades",
    ("buscar_maiores_quantidades", "terra_indigena"):       "buscar_maiores_quantidades",
    ("buscar_maiores_quantidades", "quilombola"):           "buscar_maiores_quantidades",
    # Documentos RAG
    ("buscar_documentos", None):                   "buscar_documentos_rag",
}

INTENCOES_INDISPONIVEIS: frozenset[str] = frozenset({
    "buscar_documentos",
    "buscar_assentamentos",
    "buscar_camadas_estaduais",
    "buscar_imoveis_em_camadas",
})

CAR_SCOPED_INTENTS: frozenset[str] = frozenset({
    "buscar_imoveis_rurais",
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
})

RA_EXCLUDED_INTENTS: frozenset[str] = frozenset({
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
})

# Argumentos das ferramentas de cross-query (mesmos da ferramenta base + extras)
_CROSS_QUERY_DATE_TOOLS: frozenset[str] = frozenset({
    "buscar_queimadas_em_unidades_conservacao",
    "buscar_queimadas_em_terras_indigenas",
    "buscar_queimadas_em_quilombolas",
    "buscar_desmatamentos_em_unidades_conservacao",
    "buscar_desmatamentos_em_terras_indigenas",
    "buscar_desmatamentos_em_quilombolas",
})


def _resolve_tool(intent: str, contexto_espacial: Optional[str]) -> Optional[str]:
    """Retorna o nome da ferramenta conforme dispatch 2D; None se desconhecido."""
    tool = DISPATCH.get((intent, contexto_espacial))
    if tool is None and contexto_espacial is not None:
        # fallback: ignora contexto_espacial desconhecido
        tool = DISPATCH.get((intent, None))
    return tool


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


def _build_tool_arguments(intent: str, tool_name: str, entities: Entidades) -> Dict[str, Any]:
    """Constrói o dict de argumentos correto para cada ferramenta."""
    args = _build_base_arguments(intent, entities)

    # Datas (queimadas, desmatamentos, focos imovel e cross-queries)
    if intent in {"buscar_queimadas", "buscar_desmatamentos", "buscar_focos_queimada_imovel"} or tool_name in _CROSS_QUERY_DATE_TOOLS:
        if entities.data_inicio:
            args["data_inicio"] = entities.data_inicio
        if entities.data_fim:
            args["data_fim"] = entities.data_fim

    # Campos específicos por ferramenta
    if tool_name in {"buscar_queimadas", "buscar_queimadas_em_unidades_conservacao",
                     "buscar_queimadas_em_terras_indigenas", "buscar_queimadas_em_quilombolas"} and entities.bioma:
        args["bioma"] = entities.bioma

    if tool_name in {"buscar_queimadas_em_unidades_conservacao",
                     "buscar_desmatamentos_em_unidades_conservacao",
                     "buscar_unidades_conservacao"}:
        if entities.categoria_uc:
            args["categoria"] = entities.categoria_uc
        if entities.esfera_uc and tool_name in {"buscar_queimadas_em_unidades_conservacao",
                                                 "buscar_unidades_conservacao"}:
            args["esfera"] = entities.esfera_uc
        if entities.grupo_snuc and tool_name == "buscar_unidades_conservacao":
            args["grupo_snuc"] = entities.grupo_snuc

    if tool_name == "buscar_terras_indigenas" and entities.fase_ti:
        args["fase"] = entities.fase_ti

    if tool_name in {"buscar_desmatamentos", "buscar_desmatamentos_em_unidades_conservacao",
                     "buscar_desmatamentos_em_terras_indigenas", "buscar_desmatamentos_em_quilombolas"}:
        if entities.tipo_alerta:
            args["tipo_alerta"] = entities.tipo_alerta

    if tool_name in {"buscar_imoveis_rurais", "buscar_passivos_em_imovel", "buscar_focos_queimada_imovel"} and entities.codigo_car:
        args["codigo_car"] = entities.codigo_car

    if tool_name == "buscar_maiores_quantidades":
        args["tema"] = entities.tema_ranking  # pode ser None (agrega todos)
        args["limite"] = getattr(entities, "limite", 3)
        args["is_ranking"] = getattr(entities, "is_ranking", False)
        if entities.bioma:
            args["bioma"] = entities.bioma

    if tool_name == "buscar_sobreposicao_areas":
        args["tema_a"] = entities.tema_sobreposicao_a
        args["tema_b"] = entities.tema_sobreposicao_b
        args["limite"] = getattr(entities, "limite", 5)

    return args


async def executar_consulta(
    session: AsyncSession,
    intent: str,
    entities: Entidades,
) -> Dict[str, Any]:
    """Executa a ferramenta correspondente a uma única intenção e retorna seu resultado."""
    if intent == "fora_escopo":
        return _empty_result("fora_escopo")

    if intent in INTENCOES_INDISPONIVEIS:
        return _empty_result(intent)

    if intent == "buscar_passivos_imovel" and not entities.codigo_car:
        logger.info("Intenção 'buscar_passivos_imovel' ignorada: código CAR não detectado.")
        return _empty_result(intent)

    tool_name = _resolve_tool(intent, entities.contexto_espacial)
    if not tool_name:
        logger.warning("Sem ferramenta mapeada para: intent=%s contexto=%s", intent, entities.contexto_espacial)
        return _empty_result(intent)

    tool_fn = TOOL_FUNCTIONS.get(tool_name)
    if not tool_fn:
        logger.error("Ferramenta '%s' não encontrada em TOOL_FUNCTIONS", tool_name)
        return _empty_result(intent)

    tool_args = _build_tool_arguments(intent, tool_name, entities)

    try:
        result = await tool_fn(session, **tool_args)
    except Exception:
        logger.exception("Erro ao executar ferramenta: %s", tool_name)
        return _empty_result(intent)

    return {
        "effective_tool": tool_name,
        "features": result.get("features", []),
        "bbox": result.get("bbox"),
        "total": result.get("total", len(result.get("features", []))),
        "fontes": result.get("fontes", []),
        "descricao": result.get("descricao", ""),
        "sql_executado": result.get("sql_executado"),
        "mensagem_erro": None,
    }


async def _executar_tarefas(
    session: AsyncSession,
    tarefas: List[Tuple[str, Entidades]],
    session_factory: Optional[Callable[[], AsyncSession]],
) -> List[Dict[str, Any]]:
    if len(tarefas) <= 1 or session_factory is None:
        return [await executar_consulta(session, intent, entidades) for intent, entidades in tarefas]

    async def _isolada(intent: str, entidades: Entidades) -> Dict[str, Any]:
        async with session_factory() as sessao:
            return await executar_consulta(sessao, intent, entidades)

    return await asyncio.gather(*[_isolada(intent, entidades) for intent, entidades in tarefas])


async def executar_plano(
    session: AsyncSession,
    tarefas: List[Tuple[str, Entidades]],
    query_embedding: Optional[List[float]],
    needs_rag: bool = False,
    session_factory: Optional[Callable[[], AsyncSession]] = None,
) -> Dict[str, Any]:
    """Executa todas as tarefas do plano e devolve um bloco de resposta por tarefa."""
    document_context = ""
    rag_sources: List[Dict[str, Any]] = []
    sql_segments: List[str] = []

    if needs_rag and query_embedding:
        try:
            rag = await buscar_documentos_rag(session, query_embedding, limite=4)
            document_context = rag.get("contexto_textual", "")
            rag_sources = rag.get("fontes", [])
            if rag.get("sql_executado"):
                sql_segments.append(rag["sql_executado"])
        except Exception:
            logger.exception("Erro ao executar busca RAG de documentos")

    resultados = await _executar_tarefas(session, tarefas, session_factory)

    blocos: List[Dict[str, Any]] = []
    for (intent, entidades), resultado in zip(tarefas, resultados):
        if resultado.get("sql_executado"):
            sql_segments.append(resultado["sql_executado"])
        eh_documento = resultado["effective_tool"] == "buscar_documentos_rag"
        fontes = resultado.get("fontes", [])
        blocos.append({
            "effective_tool": resultado["effective_tool"],
            "entities": entidades,
            "total_features": len(resultado.get("features") or []),
            "sources": _merge_sources(fontes, rag_sources) if eh_documento else fontes,
            "document_context": document_context if eh_documento else "",
            "query_description": resultado.get("descricao"),
            "features": resultado.get("features") or [],
            "bbox": resultado.get("bbox"),
        })

    return {
        "blocos": blocos,
        "document_context": document_context,
        "sql_executado": "\n\n".join(sql_segments) if sql_segments else None,
    }


def _merge_sources(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for source in [*primary, *secondary]:
        merged.setdefault(source["nome"], source)
    return list(merged.values())


def _empty_result(effective_tool: str) -> Dict[str, Any]:
    return {
        "effective_tool": effective_tool,
        "features": [],
        "bbox": None,
        "total": 0,
        "fontes": [],
        "descricao": "",
        "sql_executado": None,
        "mensagem_erro": None,
    }
