# -*- coding: utf-8 -*-
"""
Formata a resposta textual do agente com base nos resultados das consultas.
Usa templates estruturados por intenção, citando as fontes.
"""
from __future__ import annotations

from typing import Any

from nlp_processor.pipeline.entity_extractor import Entidades

# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------


def _fmt_num(value: int | float, decimals: int = 0) -> str:
    """Formata número no padrão brasileiro (1.234,56)."""
    if decimals == 0:
        formatted = f"{int(value):,}".replace(",", ".")
        return formatted
    formatted = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


# ---------------------------------------------------------------------------
# Templates por intenção
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "buscar_queimadas": (
        "Com base nos dados do **{fonte_principal}**, foram identificados "
        "**{total_fmt} focos de queimada**{escopo}. "
        "{detalhe_periodo}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_desmatamentos": (
        "De acordo com os alertas do **{fonte_principal}**, foram encontrados "
        "**{total_fmt} alertas de desmatamento**{escopo}. "
        "{detalhe_periodo}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_unidades_conservacao": (
        "O sistema registra **{total_fmt} unidades de conservação**{escopo}, "
        "conforme o Cadastro Nacional de Unidades de Conservação (CNUC) do **{fonte_principal}**. "
        "{detalhe_categoria}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_terras_indigenas": (
        "Segundo dados da **{fonte_principal}**, foram encontradas "
        "**{total_fmt} terras indígenas**{escopo}. "
        "{detalhe_fase}"
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_assentamentos": (
        "Com base no acervo fundiário do **{fonte_principal}**, existem "
        "**{total_fmt} assentamentos rurais**{escopo}. "
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_quilombolas": (
        "De acordo com o **{fonte_principal}**, foram identificados "
        "**{total_fmt} territórios quilombolas**{escopo}. "
        "{contexto}"
        "\n\n{fontes_citadas}"
    ),
    "buscar_imoveis_rurais": (
        "O Cadastro Ambiental Rural (**{fonte_principal}**) registra "
        "**{total_fmt} imóveis rurais**{escopo}. "
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
    elif entidades.regiao_administrativa:
        partes.append(f" na **{entidades.regiao_administrativa}**")
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


_TIPO_IMOVEL_POR_INTENCAO = {
    "buscar_imoveis_queimada": "imovel_rural_queimada",
    "buscar_imoveis_desmatamento": "imovel_rural_desmatamento",
    "buscar_imoveis_quilombo": "imovel_rural_quilombo",
    "buscar_imoveis_ti": "imovel_rural_ti",
}


def _detalhar_passivos_imovel(
    features: list[dict] | None,
    limite_por_tipo: int = 5,
) -> str:
    """Para `buscar_passivos_imovel`: lista nomes de UCs/TIs/quilombos com sobreposição."""
    if not features:
        return ""

    grupos: list[tuple[str, str]] = [
        ("unidade_conservacao", "Unidades de Conservação"),
        ("terra_indigena", "Terras Indígenas"),
        ("quilombo", "Territórios Quilombolas"),
    ]

    blocos: list[str] = []
    for tipo, titulo in grupos:
        items = [
            f.get("properties", {})
            for f in features
            if f.get("properties", {}).get("tipo") == tipo
        ]
        if not items:
            continue

        cabecalho = (
            f"**{titulo} ({_fmt_num(len(items))}):**"
            if len(items) <= limite_por_tipo
            else f"**{titulo} (top {limite_por_tipo} de {_fmt_num(len(items))}):**"
        )
        linhas = [cabecalho]
        for prop in items[:limite_por_tipo]:
            partes = [str(prop.get("nome") or "(sem nome)")]
            categoria = prop.get("categoria")
            if categoria:
                partes.append(str(categoria))
            pct = prop.get("percentual_sobreposicao")
            if pct:
                partes.append(f"{pct:.2f}% sobreposto".replace(".", ","))
            area = prop.get("area_intersecao_ha")
            if area:
                partes.append(f"{area:.2f} ha intersectados".replace(".", ","))
            linhas.append("- " + " — ".join(partes))
        if len(items) > limite_por_tipo:
            linhas.append(f"- … e mais {_fmt_num(len(items) - limite_por_tipo)} no mapa.")
        blocos.append("\n".join(linhas))

    return "\n\n".join(blocos)


def _listar_imoveis_afetados(
    features: list[dict] | None,
    intencao: str,
    limite: int = 10,
) -> str:
    """Gera bloco markdown com codigo_car dos imóveis retornados pela tool de relação."""
    tipo_alvo = _TIPO_IMOVEL_POR_INTENCAO.get(intencao)
    if not features or not tipo_alvo:
        return ""

    imoveis = [
        f.get("properties", {})
        for f in features
        if f.get("properties", {}).get("tipo") == tipo_alvo
    ]
    if not imoveis:
        return ""

    titulo = (
        f"**Imóveis afetados (top {min(len(imoveis), limite)} de {_fmt_num(len(imoveis))}):**"
        if len(imoveis) > limite
        else f"**Imóveis afetados ({_fmt_num(len(imoveis))}):**"
    )
    linhas = [titulo]
    for prop in imoveis[:limite]:
        codigo = prop.get("codigo_car") or "(sem CAR)"
        partes = [f"`{codigo}`"]
        nome = prop.get("nome_imovel")
        if nome:
            partes.append(str(nome))

        if intencao == "buscar_imoveis_queimada":
            n = prop.get("num_queimadas")
            if n:
                partes.append(f"{_fmt_num(n)} foco(s)")
            risco = prop.get("nivel_risco_ambiental")
            if risco:
                partes.append(f"risco {risco}")
        elif intencao == "buscar_imoveis_desmatamento":
            n = prop.get("num_alertas_desmatamento")
            if n:
                partes.append(f"{_fmt_num(n)} alerta(s)")
            area = prop.get("area_total_intersecao_ha")
            if area:
                partes.append(f"{area:.2f} ha intersectados".replace(".", ","))
        elif intencao in ("buscar_imoveis_quilombo", "buscar_imoveis_ti"):
            pct = prop.get("percentual_sobreposicao")
            if pct:
                partes.append(f"{pct:.1f}% sobreposto".replace(".", ","))

        linhas.append("- " + " — ".join(partes))

    if len(imoveis) > limite:
        linhas.append(f"- … e mais {_fmt_num(len(imoveis) - limite)} imóvel(is) no mapa.")

    return "\n".join(linhas)


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
    features: list[dict] | None = None,
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
        total_focos = sum(
            1
            for feature in (features or [])
            if feature.get("properties", {}).get("tipo") == "queimada"
        )
        if not features:
            total_focos = total_features
        texto = (
            f"Na propriedade rural **{codigo}**, foram identificados "
            f"**{_fmt_num(total_focos)} focos de queimada**{periodo}."
        )
        texto = _anexar_descricao(texto, descricao_consulta)
        if fontes_str:
            texto = f"{texto}\n\n{fontes_str}"
        return _aplicar_feedback_contexto(texto, feedback_contexto)

    if intencao == "buscar_passivos_imovel":
        # A tool já monta um cabeçalho com nome/CAR/município/área e a lista
        # de passivos. Se faltar (caso de erro/imóvel não encontrado), cai num
        # texto mínimo com o código.
        if descricao_consulta:
            texto = descricao_consulta
        else:
            codigo = entidades.codigo_car or "(codigo nao informado)"
            texto = (
                f"Passivos ambientais encontrados para a propriedade rural **{codigo}**."
            )
        detalhamento = _detalhar_passivos_imovel(features)
        if detalhamento:
            texto = f"{texto}\n\n{detalhamento}"
        if fontes_str:
            texto = f"{texto}\n\n{fontes_str}"
        return _aplicar_feedback_contexto(texto, feedback_contexto)

    # Intenções de relação (imóveis × queimada/desmatamento/quilombo/TI):
    # a tool retorna uma descrição rica com contagens já formatadas.
    if intencao in (
        "buscar_imoveis_queimada",
        "buscar_imoveis_desmatamento",
        "buscar_imoveis_quilombo",
        "buscar_imoveis_ti",
    ) and total_features > 0:
        texto = descricao_consulta or (
            f"Foram encontrados {_fmt_num(total_features)} resultados{escopo}."
        )
        listagem_imoveis = _listar_imoveis_afetados(features, intencao)
        if listagem_imoveis:
            texto = f"{texto}\n\n{listagem_imoveis}"
        if fontes_str:
            texto = f"{texto}\n\n{fontes_str}"
        return _aplicar_feedback_contexto(texto, feedback_contexto)

    # Ranking de municípios: a tool já monta o texto com o líder do ranking e
    # a lista ordenada. Aqui só anexamos as fontes consultadas.
    if intencao == "ranking_municipios":
        texto = descricao_consulta or (
            f"Não foram encontrados dados suficientes para gerar o ranking{escopo}."
        )
        if fontes_str:
            texto = f"{texto}\n\n{fontes_str}"
        return _aplicar_feedback_contexto(texto, feedback_contexto)

    # Sem dados
    if intencao != "fora_escopo" and intencao != "buscar_documentos" and total_features == 0:
        if descricao_consulta:
            return _aplicar_feedback_contexto(descricao_consulta, feedback_contexto)

        nomes = ", ".join(f["nome"] for f in fontes) if fontes else "fontes do sistema"
        return _aplicar_feedback_contexto(
            _TEMPLATES["sem_dados"].format(fontes_citadas=nomes or "fontes do sistema"),
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
            total_fmt=_fmt_num(total_features),
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
        texto = f"Foram encontrados {_fmt_num(total_features)} resultado(s){escopo}.\n\n{fontes_str}"
        texto = _anexar_descricao(texto, descricao_consulta)
        return _aplicar_feedback_contexto(texto, feedback_contexto)
