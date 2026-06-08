# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from nlp_processor.pipeline.entity_extractor import Entidades

logger = logging.getLogger(__name__)

_TEMPLATES: Dict[str, str] = {
    "buscar_queimadas": (
        "Com base nos dados do **{main_source}**, foram identificados "
        "**{total_formatted} focos de queimada**{scope}. "
        "{period_detail}"
    ),
    "buscar_desmatamentos": (
        "De acordo com os alertas do **{main_source}**, foram encontrados "
        "**{total_formatted} alertas de desmatamento**{scope}. "
        "{period_detail}"
    ),
    "buscar_unidades_conservacao": (
        "O sistema registra **{total_formatted} unidades de conservação**{scope}, "
        "conforme o Cadastro Nacional de Unidades de Conservação (CNUC) do **{main_source}**. "
        "{category_detail}"
    ),
    "buscar_terras_indigenas": (
        "Segundo dados da **{main_source}**, foram encontradas "
        "**{total_formatted} terras indígenas**{scope}. "
        "{phase_detail}"
    ),
    "buscar_quilombolas": (
        "De acordo com o **{main_source}**, foram identificados "
        "**{total_formatted} territórios quilombolas**{scope}."
    ),
    "buscar_imoveis_rurais": (
        "O Cadastro Ambiental Rural (**{main_source}**) registra "
        "**{total_formatted} imóveis rurais**{scope}."
    ),
    "buscar_documentos": (
        "Com base na base de conhecimento documental do sistema:\n\n"
        "{document_context}"
    ),
    "buscar_maiores_quantidades": (
        "Análise agregada de densidade geoespacial via **{main_source}**:\n"
        "Foram consolidados **{total_formatted} registros volumétricos**{scope}."
    ),
    "fora_escopo": (
        "Esta pergunta está fora do escopo do sistema. "
        "O assistente é especializado em análises geográficas e ambientais "
        "do estado de São Paulo, abrangendo: queimadas, desmatamento, "
        "unidades de conservação, terras indígenas, assentamentos rurais, "
        "territórios quilombolas e imóveis rurais (CAR)."
    ),
}

_PROPERTY_TYPE_BY_INTENT: Dict[str, str] = {
    "buscar_imoveis_queimada": "imovel_rural_queimada",
    "buscar_imoveis_desmatamento": "imovel_rural_desmatamento",
    "buscar_imoveis_quilombo": "imovel_rural_quilombo",
    "buscar_imoveis_ti": "imovel_rural_ti",
}


def _format_number(value: int | float, decimals: int = 0) -> str:
    if decimals == 0:
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_scope(entities: Entidades) -> str:
    parts = []
    if entities.municipio:
        parts.append(f" no município de **{entities.municipio}**")
    elif entities.regiao_administrativa:
        parts.append(f" na **{entities.regiao_administrativa}**")
    else:
        parts.append(" no estado de **São Paulo**")

    if entities.data_inicio and entities.data_fim:
        parts.append(f" entre {entities.data_inicio} e {entities.data_fim}")
    elif entities.data_inicio:
        parts.append(f" a partir de {entities.data_inicio}")
    elif entities.ano:
        parts.append(f" em {entities.ano}")

    return "".join(parts)


def _format_sources(sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return ""
    lines = ["**Fontes consultadas:**"]
    for source in sources:
        name = source.get("nome", "")
        agency = source.get("orgao", "")
        url = source.get("url", "")
        line = f"- {name}"
        if agency:
            line += f" ({agency})"
        if url:
            line += f" — {url}"
        lines.append(line)
    return "\n".join(lines)


def _get_main_source(sources: List[Dict[str, Any]]) -> str:
    return sources[0]["nome"] if sources else "fonte desconhecida"


def _apply_context_feedback(text: str, feedback_context: Optional[Dict[str, Any]]) -> str:
    if not feedback_context:
        return text
    evaluation = feedback_context.get("avaliacao")
    if evaluation == -1:
        return (
            "Considerando que o feedback anterior foi negativo, vou reformular a "
            "resposta de forma mais objetiva e com foco direto na nova solicitação.\n\n"
            f"{text}"
        )
    if evaluation == 1:
        return (
            "Considerando que o feedback anterior foi positivo, vou manter a linha "
            "de resposta e complementar o que foi pedido agora.\n\n"
            f"{text}"
        )
    return text


def _append_query_description(text: str, query_description: Optional[str]) -> str:
    if not query_description:
        return text
    return f"{text}\n\n{query_description}"


def _detail_property_liabilities(features: Optional[List[Dict[str, Any]]], limit: int = 5) -> str:
    if not features:
        return ""
    groups = [
        ("unidade_conservacao", "Unidades de Conservação"),
        ("terra_indigena", "Terras Indígenas"),
        ("quilombo", "Territórios Quilombolas"),
    ]
    blocks = []
    for group_type, title in groups:
        items = [
            f.get("properties", {})
            for f in features
            if f.get("properties", {}).get("tipo") == group_type
        ]
        if not items:
            continue
        header = f"**{title} ({_format_number(len(items))}):**" if len(items) <= limit else f"**{title} (top {limit} de {_format_number(len(items))}):**"
        lines = [header]
        for props in items[:limit]:
            parts = [str(props.get("nome") or "(sem nome)")]
            category = props.get("categoria")
            if category:
                parts.append(str(category))
            percentage = props.get("percentual_sobreposicao")
            if percentage:
                parts.append(f"{percentage:.2f}% sobreposto".replace(".", ","))
            area = props.get("area_intersecao_ha")
            if area:
                parts.append(f"{area:.2f} ha intersectados".replace(".", ","))
            lines.append("- " + " — ".join(parts))
        if len(items) > limit:
            lines.append(f"- … e mais {_format_number(len(items) - limit)} no mapa.")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _list_affected_properties(features: Optional[List[Dict[str, Any]]], intent: str, limit: int = 10) -> str:
    target_type = _PROPERTY_TYPE_BY_INTENT.get(intent)
    if not features or not target_type:
        return ""
    properties = [
        f.get("properties", {})
        for f in features
        if f.get("properties", {}).get("tipo") == target_type
    ]
    if not properties:
        return ""
    title = f"**Imóveis afetados (top {min(len(properties), limit)} de {_format_number(len(properties))}):**" if len(properties) > limit else f"**Imóveis afetados ({_format_number(len(properties))}):**"
    lines = [title]
    for props in properties[:limit]:
        car_code = props.get("codigo_car") or "(sem CAR)"
        parts = [f"`{car_code}`"]
        name = props.get("nome_imovel")
        if name:
            parts.append(str(name))
        if intent == "buscar_imoveis_queimada":
            count = props.get("num_queimadas")
            if count:
                parts.append(f"{_format_number(count)} foco(s)")
            risk = props.get("nivel_risco_ambiental")
            if risk:
                parts.append(f"risco {risk}")
        elif intent == "buscar_imoveis_desmatamento":
            count = props.get("num_alertas_desmatamento")
            if count:
                parts.append(f"{_format_number(count)} alerta(s)")
            area = props.get("area_total_intersecao_ha")
            if area:
                parts.append(f"{area:.2f} ha intersectados".replace(".", ","))
        elif intent in ("buscar_imoveis_quilombo", "buscar_imoveis_ti"):
            percentage = props.get("percentual_sobreposicao")
            if percentage:
                parts.append(f"{percentage:.1f}% sobreposto".replace(".", ","))
        lines.append("- " + " — ".join(parts))
    if len(properties) > limit:
        lines.append(f"- … e mais {_format_number(len(properties) - limit)} imóvel(is) no mapa.")
    return "\n".join(lines)


def _handle_disabled_settlements(entities: Entidades, features: Optional[List[Dict[str, Any]]], total_features: int, sources: List[Dict[str, Any]], scope: str, document_context: str) -> str:
    return "A consulta de assentamentos rurais está desativada no momento, pois a fonte não está disponível."


def _handle_wildfire_focus_property(entities: Entidades, features: Optional[List[Dict[str, Any]]], total_features: int, sources: List[Dict[str, Any]], scope: str, document_context: str) -> str:
    if total_features == 0:
        return f"Não foram encontrados focos de queimada cadastrados para o imóvel rural **{entities.codigo_car or '(codigo nao informado)'}**{scope}."
    period = ""
    if entities.data_inicio and entities.data_fim:
        period = f" no período entre {entities.data_inicio} e {entities.data_fim}"
    elif entities.data_inicio:
        period = f" a partir de {entities.data_inicio}"
    car_code = entities.codigo_car or "(codigo nao informado)"
    total_focus = sum(1 for f in (features or []) if f.get("properties", {}).get("tipo") == "queimada")
    if not features:
        total_focus = total_features
    return f"Na propriedade rural **{car_code}**, foram identificados " f"**{_format_number(total_focus)} focos de queimada**{period}."


def _handle_property_liabilities(entities: Entidades, features: Optional[List[Dict[str, Any]]], total_features: int, sources: List[Dict[str, Any]], scope: str, document_context: str) -> str:
    if total_features == 0:
        return f"Nenhum passivo ambiental ou sobreposição com áreas protegidas foi identificado para o imóvel **{entities.codigo_car or '(codigo nao informado)'}**."
    text = f"Passivos ambientais encontrados para a propriedade rural **{entities.codigo_car or '(codigo nao informado)'}**."
    details = _detail_property_liabilities(features)
    if details:
        text = f"{text}\n\n{details}"
    return text


def _handle_relational_properties(entities: Entidades, features: Optional[List[Dict[str, Any]]], total_features: int, sources: List[Dict[str, Any]], scope: str, document_context: str, intent: str = "") -> str:
    if total_features == 0:
        cleaned_intent = intent.replace("buscar_imoveis_", "")
        return f"Nenhum imóvel rural cruzando com dados de {cleaned_intent} foi encontrado{scope}."
    text = f"Foram encontrados imóveis afetados associados à consulta de {intent.replace('buscar_imoveis_', '')}{scope}."
    properties_list = _list_affected_properties(features, intent)
    if properties_list:
        text = f"{text}\n\n{properties_list}"
    return text


_STRATEGY_MAP: Dict[str, Callable[[Entidades, Optional[List[Dict[str, Any]]], int, List[Dict[str, Any]], str, str], str]] = {
    "buscar_assentamentos": _handle_disabled_settlements,
    "buscar_focos_queimada_imovel": _handle_wildfire_focus_property,
    "buscar_passivos_imovel": _handle_property_liabilities,
    "buscar_imoveis_queimada": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_queimada"),
    "buscar_imoveis_desmatamento": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_desmatamento"),
    "buscar_imoveis_quilombo": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_quilombo"),
    "buscar_imoveis_ti": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_ti"),
}


def format_pipeline_response(
    intents: List[tuple[str, float]],
    entities: Entidades,
    total_features: int,
    sources: List[Dict[str, Any]],
    document_context: str,
    query_description: Optional[str] = None,
    feedback_context: Optional[Dict[str, Any]] = None,
    features: Optional[List[Dict[str, Any]]] = None,
) -> str:
    if not intents:
        return _apply_context_feedback(_TEMPLATES["fora_escopo"], feedback_context)

    scope = _format_scope(entities)
    response_segments: List[str] = []

    for intent, confidence in intents:
        if intent == "fora_escopo":
            continue

        if intent in _STRATEGY_MAP:
            strategy_text = _STRATEGY_MAP[intent](entities, features, total_features, sources, scope, document_context)
            if strategy_text:
                response_segments.append(strategy_text)
            continue

        if total_features == 0:
            cleaned_intent = intent.replace("buscar_", "")
            response_segments.append(f"Não foram mapeados dados de {cleaned_intent}{scope} para os filtros selecionados.")
            continue

        template = _TEMPLATES.get(intent)
        if not template:
            continue

        try:
            formatted_segment = template.format(
                total=total_features,
                total_formatted=_format_number(total_features),
                scope=scope,
                main_source=_get_main_source(sources),
                document_context="",
                period_detail=f"O período analisado vai de {entities.data_inicio} a {entities.data_fim}. " if entities.data_inicio and entities.data_fim else "",
                category_detail=f"Filtro por categoria: **{entities.categoria_uc}**. " if entities.categoria_uc else "",
                phase_detail=f"Fase de demarcação: **{entities.fase_ti}**. " if entities.fase_ti else "",
            )
            response_segments.append(formatted_segment)
        except KeyError:
            response_segments.append(f"Consulta executada para a intenção: {intent}{scope}.")

    if not response_segments:
        primary_intent = intents[0][0]
        if primary_intent == "fora_escopo":
            return _apply_context_feedback(_TEMPLATES["fora_escopo"], feedback_context)
        if query_description:
            return _apply_context_feedback(query_description, feedback_context)
        
        source_names = ", ".join(s["nome"] for s in sources) if sources else "fontes oficiais"
        return _apply_context_feedback(f"Não foram localizados registros nas {source_names} para esta solicitação.", feedback_context)

    final_text = "\n\n".join(response_segments)

    if document_context:
        final_text += f"\n\n**Contexto documental:** {document_context[:500]}..."

    final_text = _append_query_description(final_text, query_description)

    cited_sources_string = _format_sources(sources)
    if cited_sources_string:
        final_text += f"\n\n{cited_sources_string}"

    return _apply_context_feedback(final_text, feedback_context)