# -*- coding: utf-8 -*-
"""
Formata a resposta textual do agente com base nos resultados das consultas.
Usa templates estruturados por intenção, citando as fontes.
"""
from __future__ import annotations

from typing import Any

from nlp_processor.pipeline.entity_extractor import Entidades

# ---------------------------------------------------------------------------
# Templates por intenção
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "buscar_queimadas": (
        "Com base nos dados do **{fonte_principal}**, foram identificados "
        "**{total} focos de queimada**{escopo}. "
        "{detalhe_periodo}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_desmatamentos": (
        "De acordo com os alertas do **{fonte_principal}**, foram encontrados "
        "**{total} alertas de desmatamento**{escopo}. "
        "{detalhe_periodo}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_unidades_conservacao": (
        "O sistema registra **{total} unidades de conservação**{escopo}, "
        "conforme o Cadastro Nacional de Unidades de Conservação (CNUC) do **{fonte_principal}**. "
        "{detalhe_categoria}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_terras_indigenas": (
        "Segundo dados da **{fonte_principal}**, foram encontradas "
        "**{total} terras indígenas**{escopo}. "
        "{detalhe_fase}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_assentamentos": (
        "Com base no acervo fundiário do **{fonte_principal}**, existem "
        "**{total} assentamentos rurais**{escopo}. "
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_quilombolas": (
        "De acordo com o **{fonte_principal}**, foram identificados "
        "**{total} territórios quilombolas**{escopo}. "
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_imoveis_rurais": (
        "O Cadastro Ambiental Rural (**{fonte_principal}**) registra "
        "**{total} imóveis rurais**{escopo}. "
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_documentos": (
        "Com base na base de conhecimento documental do sistema:\n\n"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "fora_escopo": (
        "Esta pergunta está fora do escopo do sistema. "
        "O assistente é especializado em análises geográficas e ambientais "
        "do estado de São Paulo, abrangendo: queimadas, desmatamento, "
        "unidades de conservação, terras indígenas, assentamentos rurais, "
        "territórios quilombolas e imóveis rurais (CAR)."
    ),
    "sem_dados": (
        "Com base nas fontes fornecidas ({fontes_citadas}), "
        "não foram encontrados dados suficientes para responder a esta pergunta."
    ),
}


def _formatar_escopo(entidades: Entidades) -> str:
    partes = []
    if entidades.municipio:
        partes.append(f" no município de **{entidades.municipio}**")
    else:
        partes.append(" no estado de **São Paulo**")

    if entidades.data_inicio and entidades.data_fim:
        partes.append(f" entre {entidades.data_inicio} e {entidades.data_fim}")
    elif entidades.data_inicio:
        partes.append(f" a partir de {entidades.data_inicio}")
    elif entidades.ano:
        partes.append(f" em {entidades.ano}")

    return "".join(partes)


def _formatar_fontes(fontes: list[dict]) -> str:
    if not fontes:
        return ""
    linhas = ["**Fontes consultadas:**"]
    for f in fontes:
        nome = f.get("nome", "")
        orgao = f.get("orgao", "")
        url = f.get("url", "")
        linha = f"- {nome}"
        if orgao:
            linha += f" ({orgao})"
        if url:
            linha += f" — {url}"
        linhas.append(linha)
    return "\n".join(linhas)


def _fonte_principal(fontes: list[dict]) -> str:
    return fontes[0]["nome"] if fontes else "fonte desconhecida"


def _aplicar_feedback_contexto(
    texto: str,
    feedback_contexto: dict[str, Any] | None,
) -> str:
    if not feedback_contexto:
        return texto

    avaliacao = feedback_contexto.get("avaliacao")
    if avaliacao == -1:
        return (
            "Considerando que o feedback anterior foi negativo, vou reformular a "
            "resposta de forma mais objetiva e com foco direto na nova solicitação.\n\n"
            f"{texto}"
        )
    if avaliacao == 1:
        return (
            "Considerando que o feedback anterior foi positivo, vou manter a linha "
            "de resposta e complementar o que foi pedido agora.\n\n"
            f"{texto}"
        )
    return texto


def _anexar_descricao(texto: str, descricao_consulta: str | None) -> str:
    if not descricao_consulta:
        return texto
    return f"{texto}\n\n{descricao_consulta}"


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def formatar_resposta(
    intencao: str,
    entidades: Entidades,
    total_features: int,
    fontes: list[dict],
    contexto_documental: str,
    confianca: float,
    descricao_consulta: str | None = None,
    feedback_contexto: dict[str, Any] | None = None,
) -> str:
    """
    Gera o texto de resposta formatado em Markdown.
    """
    fontes_str = _formatar_fontes(fontes)
    escopo = _formatar_escopo(entidades)

    if intencao == "buscar_assentamentos":
        return _aplicar_feedback_contexto(
            "A consulta de assentamentos rurais está desativada no momento, pois a fonte não está disponível.",
            feedback_contexto,
        )

    if intencao == "buscar_focos_queimada_imovel":
        periodo = ""
        if entidades.data_inicio and entidades.data_fim:
            periodo = f" no período entre {entidades.data_inicio} e {entidades.data_fim}"
        elif entidades.data_inicio:
            periodo = f" a partir de {entidades.data_inicio}"

        codigo = entidades.codigo_car or "(codigo nao informado)"
        texto = (
            f"Na propriedade rural **{codigo}**, foram identificados "
            f"**{total_features} focos de queimada**{periodo}."
        )
        texto = _anexar_descricao(texto, descricao_consulta)
        if fontes_str:
            texto = f"{texto}\n\n{fontes_str}"
        return _aplicar_feedback_contexto(texto, feedback_contexto)

    # Sem dados
    if intencao != "fora_escopo" and intencao != "buscar_documentos" and total_features == 0:
        nomes = ", ".join(f["nome"] for f in fontes) if fontes else "fontes do sistema"
        return _aplicar_feedback_contexto(
            _TEMPLATES["sem_dados"].format(fontes_citadas=nomes),
            feedback_contexto,
        )

    if intencao == "fora_escopo":
        return _aplicar_feedback_contexto(_TEMPLATES["fora_escopo"], feedback_contexto)

    ctx_bloco = ""
    if contexto_documental:
        ctx_bloco = f"\n\n**Contexto documental:** {contexto_documental[:500]}..."

    template = _TEMPLATES.get(intencao, _TEMPLATES["sem_dados"])

    try:
        texto = template.format(
            total=total_features,
            escopo=escopo,
            fonte_principal=_fonte_principal(fontes),
            fontes_citadas=fontes_str,
            contexto=ctx_bloco,
            detalhe_periodo=(
                f"O período analisado vai de {entidades.data_inicio} a {entidades.data_fim}. "
                if entidades.data_inicio and entidades.data_fim
                else ""
            ),
            detalhe_categoria=(
                f"Filtro por categoria: **{entidades.categoria_uc}**. "
                if entidades.categoria_uc
                else ""
            ),
            detalhe_fase=(
                f"Fase de demarcação: **{entidades.fase_ti}**. "
                if entidades.fase_ti
                else ""
            ),
        )
        texto = _anexar_descricao(texto, descricao_consulta)
        return _aplicar_feedback_contexto(texto, feedback_contexto)
    except KeyError:
        texto = f"Foram encontrados {total_features} resultado(s){escopo}.\n\n{fontes_str}"
        texto = _anexar_descricao(texto, descricao_consulta)
        return _aplicar_feedback_contexto(texto, feedback_contexto)
