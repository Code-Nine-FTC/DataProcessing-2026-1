# -*- coding: utf-8 -*-
from __future__ import annotations

from nlp_processor.domain.contracts import Fonte, RespostaNLP, ToolResult
from nlp_processor.domain.enums import Dominio, Operacao

_LABELS: dict[Dominio, str] = {
    Dominio.QUEIMADA: "focos de queimada",
    Dominio.DESMATAMENTO: "alertas de desmatamento",
    Dominio.UNIDADE_CONSERVACAO: "unidades de conservação",
    Dominio.TERRA_INDIGENA: "terras indígenas",
    Dominio.QUILOMBOLA: "territórios quilombolas",
    Dominio.ASSENTAMENTO: "assentamentos rurais",
    Dominio.IMOVEL_RURAL: "imóveis rurais",
    Dominio.CAMADA_ESTADUAL: "camadas estaduais",
    Dominio.DOCUMENTO: "documentos",
}


def _fmt_int(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _escopo(resultado: ToolResult) -> str:
    onde = resultado.spec.onde
    if onde.municipio_nome:
        return f" em **{onde.municipio_nome}**"
    if onde.regiao_administrativa_nome:
        return f" na **{onde.regiao_administrativa_nome}**"
    if onde.codigo_car:
        return f" no imóvel **{onde.codigo_car}**"
    return " em **São Paulo**"


def _periodo(resultado: ToolResult) -> str:
    p = resultado.spec.periodo
    if not p:
        return ""
    if p.data_inicio and p.data_fim:
        return f" entre {p.data_inicio} e {p.data_fim}"
    if p.data_inicio:
        return f" a partir de {p.data_inicio}"
    return ""


def _contexto_espacial(resultado: ToolResult) -> str:
    ctx = resultado.spec.contexto_espacial
    if not ctx or not ctx.dentro_de:
        return ""
    labels = {
        Dominio.TERRA_INDIGENA: "dentro de terras indígenas",
        Dominio.UNIDADE_CONSERVACAO: "dentro de unidades de conservação",
        Dominio.QUILOMBOLA: "dentro de territórios quilombolas",
        Dominio.ASSENTAMENTO: "dentro de assentamentos rurais",
        Dominio.QUEIMADA: "com foco de queimada",
        Dominio.DESMATAMENTO: "com alerta de desmatamento",
    }
    return f" {labels.get(ctx.dentro_de, '')}"


def _medida_ranking(propriedades: dict) -> str:
    unidade = propriedades.get("unidade") or propriedades.get("label") or ""
    qtd = propriedades.get("qtd")
    if qtd is not None:
        base = f"{_fmt_int(int(qtd))} {unidade}".strip()
        area = propriedades.get("area_ha")
        return f"{base} ({_fmt_int(int(area))} ha)" if area else base
    return f"{_fmt_int(int(propriedades.get('valor') or 0))} {unidade}".strip()


def _renderizar_ranking(resultado: ToolResult, label: str) -> str:
    ranking = sorted(
        (f["properties"] for f in resultado.features),
        key=lambda p: p.get("posicao", 9999),
    )
    if not ranking:
        return f"Nenhum dado de ranking encontrado para {label}."

    lider = ranking[0]
    abertura = f"**{lider.get('municipio', '—')}** é o município com mais {label}: {_medida_ranking(lider)}."
    if len(ranking) == 1:
        return abertura

    linhas = [abertura, ""]
    for p in ranking:
        linhas.append(f"{p.get('posicao')}. **{p.get('municipio', '—')}** — {_medida_ranking(p)}")
    return "\n".join(linhas)


def _renderizar_imovel_car(resultado: ToolResult) -> str:
    car = resultado.spec.onde.codigo_car
    imovel = next(
        (f["properties"] for f in resultado.features if f["properties"].get("tipo") == "imovel_rural"),
        None,
    )
    if not imovel:
        return f"Não foi encontrado nenhum imóvel rural com o CAR **{car}**."
    municipio = imovel.get("municipio") or "São Paulo"
    area = imovel.get("area_ha")
    area_txt = f", com área de {_fmt_int(int(area))} ha" if area else ""
    return f"O imóvel rural **{car}** está localizado em **{municipio}**{area_txt}."


def _renderizar(resultado: ToolResult) -> str:
    label = _LABELS.get(resultado.dominio, resultado.dominio.value)
    total = _fmt_int(resultado.total)
    escopo = _escopo(resultado)
    periodo = _periodo(resultado)
    contexto = _contexto_espacial(resultado)

    if resultado.operacao == Operacao.LISTAR and resultado.dominio == Dominio.IMOVEL_RURAL and resultado.spec.onde.codigo_car:
        return _renderizar_imovel_car(resultado)

    if resultado.operacao == Operacao.RANKEAR:
        return _renderizar_ranking(resultado, label)

    if resultado.operacao == Operacao.PASSIVOS:
        return f"Passivos ambientais{escopo}: {total} ocorrências identificadas."

    if resultado.operacao == Operacao.SOBREPOR:
        return f"Sobreposição de **{label}**{escopo}: {total} intersecções encontradas."

    if resultado.total == 0:
        return f"Nenhum {label} encontrado{escopo}{periodo}{contexto}."

    return f"Encontrados **{total}** {label}{escopo}{periodo}{contexto}."


def _coletar_fontes(resultados: list[ToolResult]) -> list[Fonte]:
    vistas: dict[str, Fonte] = {}
    for resultado in resultados:
        for fonte in resultado.fontes:
            if fonte.nome not in vistas:
                vistas[fonte.nome] = fonte
    return list(vistas.values())


def _coletar_features(resultados: list[ToolResult]) -> list[dict]:
    features: list[dict] = []
    for resultado in resultados:
        features.extend(resultado.features)
    return features


def _coletar_bbox(resultados: list[ToolResult]) -> list[float] | None:
    for resultado in resultados:
        if resultado.bbox:
            return resultado.bbox
    return None


def _coletar_sql(resultados: list[ToolResult]) -> str | None:
    sqls = [r.sql_executado for r in resultados if r.sql_executado]
    return "\n\n---\n\n".join(sqls) if sqls else None


def compor(
    resultados: list[ToolResult],
) -> RespostaNLP:
    if not resultados:
        return RespostaNLP(
            texto="Não foram encontrados resultados para sua consulta.",
            features=[],
            bbox=None,
            fontes=[],
            status="sem_resultado",
            confianca=0.0,
        )

    linhas = [_renderizar(r) for r in resultados]
    texto = "\n\n".join(linhas)

    total_geral = sum(r.total for r in resultados)
    status = "sucesso" if total_geral > 0 else "sem_resultado"
    confianca = max((r.spec.filtros.limite / 100.0 for r in resultados), default=0.5)

    return RespostaNLP(
        texto=texto,
        features=_coletar_features(resultados),
        bbox=_coletar_bbox(resultados),
        fontes=_coletar_fontes(resultados),
        status=status,
        confianca=min(confianca, 1.0),
        sql_executado=_coletar_sql(resultados),
    )
