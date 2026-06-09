# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from nlp_processor.pipeline.entity_extractor import Entidades

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Templates de resposta — chaveados pelo nome da ferramenta efetiva (effective_tool)
# ---------------------------------------------------------------------------
_TEMPLATES: Dict[str, str] = {
    "buscar_queimadas": (
        "Com base nos dados do **{main_source}**, foram identificados "
        "**{total_formatted} focos de queimada**{scope}. "
        "{period_detail}"
    ),
    "buscar_queimadas_em_unidades_conservacao": (
        "Foram identificados **{total_formatted} focos de queimada em unidades de conservação**{scope}. "
        "{period_detail}"
    ),
    "buscar_queimadas_em_terras_indigenas": (
        "Foram identificados **{total_formatted} focos de queimada em terras indígenas**{scope}. "
        "{period_detail}"
    ),
    "buscar_queimadas_em_quilombolas": (
        "Foram identificados **{total_formatted} focos de queimada em territórios quilombolas**{scope}. "
        "{period_detail}"
    ),
    "buscar_desmatamentos": (
        "De acordo com os alertas do **{main_source}**, foram encontrados "
        "**{total_formatted} alertas de desmatamento**{scope}. "
        "{period_detail}"
    ),
    "buscar_desmatamentos_em_unidades_conservacao": (
        "Foram encontrados **{total_formatted} alertas de desmatamento em unidades de conservação**{scope}. "
        "{period_detail}"
    ),
    "buscar_desmatamentos_em_terras_indigenas": (
        "Foram encontrados **{total_formatted} alertas de desmatamento em terras indígenas**{scope}. "
        "{period_detail}"
    ),
    "buscar_desmatamentos_em_quilombolas": (
        "Foram encontrados **{total_formatted} alertas de desmatamento em territórios quilombolas**{scope}. "
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
    "buscar_territorios_quilombolas": (
        "De acordo com o **{main_source}**, foram identificados "
        "**{total_formatted} territórios quilombolas**{scope}."
    ),
    "buscar_imoveis_rurais": (
        "O Cadastro Ambiental Rural (**{main_source}**) registra "
        "**{total_formatted} imóveis rurais**{scope}."
    ),
    "buscar_documentos_rag": (
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

_MENSAGEM_SEM_DOCUMENTO = (
    "Não encontrei conteúdo relevante na base de conhecimento documental do sistema "
    "para responder a essa pergunta."
)

_PROPERTY_TYPE_BY_TOOL: Dict[str, str] = {
    "buscar_imoveis_por_queimada":       "imovel_rural_queimada",
    "buscar_imoveis_por_desmatamento":   "imovel_rural_desmatamento",
    "buscar_imoveis_por_quilombo":       "imovel_rural_quilombo",
    "buscar_imoveis_por_terra_indigena": "imovel_rural_ti",
}


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

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


def _should_append_description(effective_tool: str, total_features: int) -> bool:
    if total_features == 0:
        return False
    return effective_tool not in _TEMPLATES and effective_tool not in _STRATEGY_MAP


# ---------------------------------------------------------------------------
# Estratégias especializadas para ferramentas específicas
# ---------------------------------------------------------------------------

def _handle_disabled_settlements(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
) -> str:
    return "A consulta de assentamentos rurais está desativada no momento, pois a fonte não está disponível."


def _handle_wildfire_focus_property(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
) -> str:
    car_code = entities.codigo_car or "(codigo nao informado)"
    if total == 0:
        return f"Não foram encontrados focos de queimada cadastrados para o imóvel rural **{car_code}**{scope}."
    period = ""
    if entities.data_inicio and entities.data_fim:
        period = f" no período entre {entities.data_inicio} e {entities.data_fim}"
    elif entities.data_inicio:
        period = f" a partir de {entities.data_inicio}"
    total_focus = sum(1 for f in (features or []) if f.get("properties", {}).get("tipo") == "queimada") or total
    return f"Na propriedade rural **{car_code}**, foram identificados **{_format_number(total_focus)} focos de queimada**{period}."


def _handle_property_liabilities(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
) -> str:
    car_code = entities.codigo_car or "(codigo nao informado)"
    if total == 0:
        return f"Nenhum passivo ambiental ou sobreposição com áreas protegidas foi identificado para o imóvel **{car_code}**."
    text = f"Passivos ambientais encontrados para a propriedade rural **{car_code}**."
    details = _detail_property_liabilities(features)
    if details:
        text = f"{text}\n\n{details}"
    return text


def _handle_maiores_quantidades(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
) -> str:
    if not features:
        return "Nenhum dado encontrado para a análise quantitativa solicitada."

    mun_entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for f in features:
        props = f.get("properties", {})
        nome = str(props.get("nome") or "").strip()
        analise = str(props.get("analise") or "").strip()
        if nome and nome not in seen:
            mun_entries.append((nome, analise))
            seen.add(nome)

    if not mun_entries:
        return "Nenhum município identificado na análise quantitativa."

    main_source = _get_main_source(sources)
    linhas = [f"**Municípios em destaque**{scope} (via {main_source}):"]
    for nome, analise in mun_entries:
        linhas.append(f"- **{nome}**: {analise}")
    return "\n".join(linhas)


def _handle_area_overlap(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
) -> str:
    if not features:
        return f"Nenhuma sobreposição entre as camadas indicadas foi encontrada{scope}."

    linhas = [f"**Municípios com maior sobreposição de áreas**{scope}:"]
    seen: set[str] = set()
    for f in features:
        props = f.get("properties", {})
        nome = str(props.get("nome") or "").strip()
        analise = str(props.get("analise") or "").strip()
        if nome and nome not in seen:
            linhas.append(f"- **{nome}**: {analise}")
            seen.add(nome)
    return "\n".join(linhas)


def _handle_relational_properties(
    entities: Entidades,
    features: Optional[List[Dict[str, Any]]],
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    document_context: str,
    tool_name: str = "",
) -> str:
    if total == 0:
        return f"Nenhum imóvel rural cruzando com os dados solicitados foi encontrado{scope}."
    text = f"Foram encontrados imóveis afetados associados à consulta{scope}."
    properties_list = _list_affected_properties(features, tool_name)
    if properties_list:
        text = f"{text}\n\n{properties_list}"
    return text


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
        items = [f.get("properties", {}) for f in features if f.get("properties", {}).get("tipo") == group_type]
        if not items:
            continue
        header = (
            f"**{title} ({_format_number(len(items))}):**"
            if len(items) <= limit
            else f"**{title} (top {limit} de {_format_number(len(items))}):**"
        )
        lines = [header]
        for props in items[:limit]:
            parts = [str(props.get("nome") or "(sem nome)")]
            if props.get("categoria"):
                parts.append(str(props["categoria"]))
            if props.get("percentual_sobreposicao"):
                parts.append(f"{props['percentual_sobreposicao']:.2f}% sobreposto".replace(".", ","))
            if props.get("area_intersecao_ha"):
                parts.append(f"{props['area_intersecao_ha']:.2f} ha intersectados".replace(".", ","))
            lines.append("- " + " — ".join(parts))
        if len(items) > limit:
            lines.append(f"- … e mais {_format_number(len(items) - limit)} no mapa.")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _list_affected_properties(features: Optional[List[Dict[str, Any]]], tool_name: str, limit: int = 10) -> str:
    target_type = _PROPERTY_TYPE_BY_TOOL.get(tool_name)
    if not features or not target_type:
        return ""
    properties = [f.get("properties", {}) for f in features if f.get("properties", {}).get("tipo") == target_type]
    if not properties:
        return ""
    title = (
        f"**Imóveis afetados (top {min(len(properties), limit)} de {_format_number(len(properties))}):**"
        if len(properties) > limit
        else f"**Imóveis afetados ({_format_number(len(properties))}):**"
    )
    lines = [title]
    for props in properties[:limit]:
        car_code = props.get("codigo_car") or "(sem CAR)"
        parts = [f"`{car_code}`"]
        if props.get("nome_imovel"):
            parts.append(str(props["nome_imovel"]))
        if tool_name == "buscar_imoveis_por_queimada":
            if props.get("num_queimadas"):
                parts.append(f"{_format_number(props['num_queimadas'])} foco(s)")
            if props.get("nivel_risco_ambiental"):
                parts.append(f"risco {props['nivel_risco_ambiental']}")
        elif tool_name == "buscar_imoveis_por_desmatamento":
            if props.get("num_alertas_desmatamento"):
                parts.append(f"{_format_number(props['num_alertas_desmatamento'])} alerta(s)")
            if props.get("area_total_intersecao_ha"):
                parts.append(f"{props['area_total_intersecao_ha']:.2f} ha intersectados".replace(".", ","))
        elif tool_name in ("buscar_imoveis_por_quilombo", "buscar_imoveis_por_terra_indigena"):
            if props.get("percentual_sobreposicao"):
                parts.append(f"{props['percentual_sobreposicao']:.1f}% sobreposto".replace(".", ","))
        lines.append("- " + " — ".join(parts))
    if len(properties) > limit:
        lines.append(f"- … e mais {_format_number(len(properties) - limit)} imóvel(is) no mapa.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registro de estratégias especializadas: tool_name → função
# ---------------------------------------------------------------------------
_STRATEGY_MAP: Dict[str, Callable] = {
    "buscar_assentamentos":           _handle_disabled_settlements,
    "buscar_focos_queimada_imovel":   _handle_wildfire_focus_property,
    "buscar_passivos_em_imovel":      _handle_property_liabilities,
    "buscar_maiores_quantidades":     _handle_maiores_quantidades,
    "buscar_sobreposicao_areas":      _handle_area_overlap,
    "buscar_imoveis_por_queimada":    lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_por_queimada"),
    "buscar_imoveis_por_desmatamento": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_por_desmatamento"),
    "buscar_imoveis_por_quilombo":    lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_por_quilombo"),
    "buscar_imoveis_por_terra_indigena": lambda e, f, t, s, sc, dc: _handle_relational_properties(e, f, t, s, sc, dc, "buscar_imoveis_por_terra_indigena"),
}


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def _render_bloco(bloco: Dict[str, Any]) -> str:
    effective_tool = bloco["effective_tool"]
    entities = bloco["entities"]
    total_features = bloco["total_features"]
    sources = bloco.get("sources", [])
    document_context = bloco.get("document_context", "")
    query_description = bloco.get("query_description")
    features = bloco.get("features")
    scope = _format_scope(entities)

    if effective_tool == "fora_escopo":
        return _TEMPLATES["fora_escopo"]

    if effective_tool == "buscar_documentos_rag":
        if not document_context:
            return _MENSAGEM_SEM_DOCUMENTO
        body = _apply_template(effective_tool, total_features, sources, scope, entities, document_context)
    elif effective_tool in _STRATEGY_MAP:
        body = _STRATEGY_MAP[effective_tool](entities, features, total_features, sources, scope, document_context)
    elif total_features == 0:
        body = _build_zero_results_message(effective_tool, entities, scope)
    else:
        body = _apply_template(effective_tool, total_features, sources, scope, entities, document_context)

    if _should_append_description(effective_tool, total_features):
        body = _append_query_description(body, query_description)

    return body


def _dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    visto: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        nome = source.get("nome")
        if nome and nome not in visto:
            visto[nome] = source
    return list(visto.values())


def compor_resposta(
    blocos: List[Dict[str, Any]],
    feedback_context: Optional[Dict[str, Any]] = None,
) -> str:
    if not blocos:
        return _apply_context_feedback(_TEMPLATES["fora_escopo"], feedback_context)

    corpos = [corpo for corpo in (_render_bloco(bloco) for bloco in blocos) if corpo]
    texto = "\n\n".join(corpos)

    fontes: List[Dict[str, Any]] = []
    for bloco in blocos:
        fontes.extend(bloco.get("sources", []))
    citacao = _format_sources(_dedupe_sources(fontes))
    if citacao:
        texto += f"\n\n{citacao}"

    return _apply_context_feedback(texto, feedback_context)


def format_pipeline_response(
    effective_tool: str,
    entities: Entidades,
    total_features: int,
    sources: List[Dict[str, Any]],
    document_context: str,
    query_description: Optional[str] = None,
    feedback_context: Optional[Dict[str, Any]] = None,
    features: Optional[List[Dict[str, Any]]] = None,
) -> str:
    bloco = {
        "effective_tool": effective_tool,
        "entities": entities,
        "total_features": total_features,
        "sources": sources,
        "document_context": document_context,
        "query_description": query_description,
        "features": features,
    }
    return compor_resposta([bloco], feedback_context)


def _apply_template(
    tool_name: str,
    total: int,
    sources: List[Dict[str, Any]],
    scope: str,
    entities: Entidades,
    document_context: str,
) -> str:
    template = _TEMPLATES.get(tool_name)
    if not template:
        return f"Consulta executada para **{tool_name}**{scope}. {_format_number(total)} registros encontrados."

    try:
        return template.format(
            total=total,
            total_formatted=_format_number(total),
            scope=scope,
            main_source=_get_main_source(sources),
            document_context=document_context,
            period_detail=(
                f"O período analisado vai de {entities.data_inicio} a {entities.data_fim}. "
                if entities.data_inicio and entities.data_fim
                else ""
            ),
            category_detail=f"Filtro por categoria: **{entities.categoria_uc}**. " if entities.categoria_uc else "",
            phase_detail=f"Fase de demarcação: **{entities.fase_ti}**. " if entities.fase_ti else "",
        )
    except KeyError:
        return f"Consulta executada para a ferramenta **{tool_name}**{scope}."


def _build_zero_results_message(tool_name: str, entities: Entidades, scope: str) -> str:
    cleaned = tool_name.replace("buscar_", "").replace("_", " ")
    has_date_filter = bool(entities.data_inicio or entities.ano)

    if not has_date_filter:
        return f"Não foram mapeados dados de {cleaned}{scope} para os filtros selecionados."

    if entities.ano:
        periodo = f" em {entities.ano}"
    elif entities.data_inicio and entities.data_fim:
        periodo = f" entre {entities.data_inicio} e {entities.data_fim}"
    else:
        periodo = f" a partir de {entities.data_inicio}"

    escopo_sem_data = scope.split(" entre ")[0].split(" em ")[0]
    return (
        f"Não foram encontrados dados de {cleaned}{escopo_sem_data}."
        f" Não há registros disponíveis{periodo} na base de dados."
        f" Tente consultar sem especificar um período para visualizar os registros mais recentes."
    )
