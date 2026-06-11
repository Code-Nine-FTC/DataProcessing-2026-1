# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np

from nlp_processor.domain.contracts import (
    ContextoEspacial,
    FiltrosConsulta,
    PlanoConsulta,
    QuerySpec,
    TextoProcessado,
)
from nlp_processor.domain import confidence
from nlp_processor.domain.enums import Dominio, Operacao
from nlp_processor.domain.vocabulary import GRUPOS, Categoria, GrupoSemantico
from nlp_processor.infrastructure.embedder import embed_batch, embed_texto

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = confidence.LIMIAR_FALLBACK
_MARGEM_DOMINANTE = 0.08

_RE_CONTEXTO_ESPACIAL = re.compile(
    r"\b(dentro\s+de|que\s+intersect[a-z]*|sobreposto[s]?\s+[aà]|"
    r"sobrepostos\s+a|cruzamento\s+entre|sobreposicao\s+com|"
    r"intersec[a-z]+\s+(com|de|entre))\b",
    re.IGNORECASE,
)

_RE_FORA_SP = re.compile(
    r"\b(bahia|ceara|pernambuco|maranhao|piaui|paraiba|sergipe|alagoas|"
    r"rio grande do [ns]ul|santa catarina|parana(?!pana)|minas gerais|"
    r"rio de janeiro|espirito santo|mato grosso|goias|tocantins|rondonia|"
    r"roraima|amapa|amazonas|amazonia|para\b|pantanal|brasilia|"
    r"distrito federal)\b"
)

_RE_CAR = re.compile(r"\b[a-z]{2}-\d{7}-[a-z0-9]{32}\b", re.IGNORECASE)
_RE_PASSIVO = re.compile(r"\b(passivo|passivos|infrac|irregularidad|sobrepos)", re.IGNORECASE)

_grupo_matrices: dict[str, np.ndarray] = {}
_grupo_rotulos: dict[str, list[str]] = {}

_KEYWORD_DOMINIO: dict[str, str] = {
    "desmatamento": "desmatamento",
    "queimada": "queimada",
    "queimadas": "queimada",
    "incendio": "queimada",
    "indigena": "terra_indigena",
    "indigenas": "terra_indigena",
    "quilombola": "quilombola",
    "quilombolas": "quilombola",
    "assentamento": "assentamento",
    "assentamentos": "assentamento",
    "imovel": "imovel_rural",
    "imoveis": "imovel_rural",
}

_RANKING_KEYWORDS: dict[Dominio, tuple[str, ...]] = {
    Dominio.QUEIMADA: ("queimada", "queimadas", "incendio", "incendios", "fogo", "foco", "focos", "calor"),
    Dominio.DESMATAMENTO: ("desmatamento", "desmatamentos", "desmatada", "desmatadas", "prodes", "deter"),
    Dominio.TERRA_INDIGENA: ("indigena", "indigenas", "ti"),
    Dominio.UNIDADE_CONSERVACAO: ("conservacao", "uc", "ucs", "parque", "parques", "protecao", "apa"),
    Dominio.QUILOMBOLA: ("quilombola", "quilombolas", "quilombo", "quilombos"),
}


async def warm_up() -> None:
    global _grupo_matrices, _grupo_rotulos

    total = 0
    for grupo in GRUPOS:
        textos: list[str] = []
        rotulos: list[str] = []
        for cat in grupo.categorias:
            for semente in cat.sementes:
                textos.append(semente)
                rotulos.append(cat.rotulo)

        if not textos:
            continue
        matrix = embed_batch(textos)
        _grupo_matrices[grupo.nome] = matrix
        _grupo_rotulos[grupo.nome] = rotulos
        total += len(textos)

    logger.info("Router aquecido: %d sementes em %d grupos.", total, len(_grupo_matrices))


def is_ready() -> bool:
    return bool(_grupo_matrices)


def _melhor_rotulo(
    vetor: np.ndarray,
    grupo: GrupoSemantico,
) -> tuple[Optional[str], float]:
    matrix = _grupo_matrices.get(grupo.nome)
    if matrix is None:
        return None, 0.0

    scores = (matrix @ vetor).tolist()
    rotulos = _grupo_rotulos[grupo.nome]

    agrupado: dict[str, float] = {}
    for rotulo, score in zip(rotulos, scores):
        if score > agrupado.get(rotulo, 0.0):
            agrupado[rotulo] = score

    if not agrupado:
        return None, 0.0

    rotulo_top = max(agrupado, key=agrupado.__getitem__)
    return rotulo_top, agrupado[rotulo_top]


def _classificar_grupo(
    vetor: np.ndarray,
    grupo: GrupoSemantico,
) -> tuple[Optional[str], float]:
    rotulo, score = _melhor_rotulo(vetor, grupo)
    if score < grupo.limiar:
        return None, score
    return rotulo, score


def _cat_para_spec(grupo: GrupoSemantico, rotulo: str) -> Optional[QuerySpec]:
    cat: Optional[Categoria] = next(
        (c for c in grupo.categorias if c.rotulo == rotulo), None
    )
    if cat is None:
        return None

    qspec = cat.query_spec
    dominio_str = qspec.get("dominio")
    operacao_str = qspec.get("operacao", "listar")

    if dominio_str is None:
        return None

    op_map = {
        "listar": Operacao.LISTAR,
        "rankear": Operacao.RANKEAR,
        "passivos": Operacao.PASSIVOS,
        "sobrepor": Operacao.SOBREPOR,
        "buscar": Operacao.LISTAR,
    }

    try:
        dominio = Dominio(dominio_str)
        operacao = op_map.get(operacao_str, Operacao.LISTAR)
    except ValueError:
        return None

    tema_ranking = qspec.get("tema_ranking")
    filtros = FiltrosConsulta(tema_ranking=tema_ranking) if tema_ranking else FiltrosConsulta()
    return QuerySpec(dominio=dominio, operacao=operacao, filtros=filtros)


def _boost_specs(
    tokens: list[str],
    vetor: np.ndarray,
    specs: list[QuerySpec],
    scores_por_dominio: dict[Dominio, float],
    melhor_score_atual: float,
) -> float:
    dominios_presentes = {s.dominio for s in specs}
    melhor = melhor_score_atual
    for token in tokens:
        nome_grupo = _KEYWORD_DOMINIO.get(token)
        if nome_grupo is None:
            continue
        try:
            dominio_kw = Dominio(nome_grupo)
        except ValueError:
            continue
        if dominio_kw in dominios_presentes:
            continue
        grupo_kw = next((g for g in GRUPOS if g.nome == nome_grupo), None)
        if grupo_kw is None:
            continue
        rotulo_kw, score_kw = _classificar_grupo(vetor, grupo_kw)
        if score_kw <= CONFIDENCE_THRESHOLD:
            continue
        if rotulo_kw is None:
            rotulo_kw, _ = _melhor_rotulo(vetor, grupo_kw)
        spec_kw = _cat_para_spec(grupo_kw, rotulo_kw)
        if spec_kw is not None:
            specs.append(spec_kw)
            dominios_presentes.add(dominio_kw)
            scores_por_dominio[spec_kw.dominio] = score_kw
            melhor = max(melhor, score_kw)
    return melhor


def _agregar_confianca(
    specs: list[QuerySpec],
    scores_por_dominio: dict[Dominio, float],
    fallback: float,
) -> float:
    pontos = [scores_por_dominio[s.dominio] for s in specs if s.dominio in scores_por_dominio]
    if not pontos:
        return fallback
    return sum(pontos) / len(pontos)


def _aplicar_margem_dominante(
    specs: list[QuerySpec],
    scores_por_dominio: dict[Dominio, float],
) -> list[QuerySpec]:
    if not scores_por_dominio:
        return specs
    top = max(scores_por_dominio.values())
    return [
        s for s in specs
        if scores_por_dominio.get(s.dominio, top) >= top - _MARGEM_DOMINANTE
    ]


_DOMINIOS_SOBREPONIVEIS = (
    Dominio.QUEIMADA,
    Dominio.DESMATAMENTO,
    Dominio.TERRA_INDIGENA,
    Dominio.UNIDADE_CONSERVACAO,
)


def _specs_para_car(texto_normalizado: str) -> list[QuerySpec]:
    operacao = Operacao.PASSIVOS if _RE_PASSIVO.search(texto_normalizado) else Operacao.LISTAR
    return [QuerySpec(dominio=Dominio.IMOVEL_RURAL, operacao=operacao)]


def _colapsar_sobreposicao_imovel(specs: list[QuerySpec], tokens: set[str]) -> list[QuerySpec]:
    if "imovel" not in tokens and "imoveis" not in tokens:
        return specs
    if not any(s.dominio == Dominio.IMOVEL_RURAL for s in specs):
        return specs

    sobreposto = next(
        (s.dominio for s in specs if s.dominio in _DOMINIOS_SOBREPONIVEIS), None
    )
    if sobreposto is None:
        return specs

    return [
        QuerySpec(
            dominio=Dominio.IMOVEL_RURAL,
            operacao=Operacao.LISTAR,
            contexto_espacial=ContextoEspacial(dentro_de=sobreposto),
        )
    ]


def _filtrar_rankings(
    specs: list[QuerySpec],
    scores_por_dominio: dict[Dominio, float],
    tokens: set[str],
) -> list[QuerySpec]:
    rankings = [s for s in specs if s.operacao == Operacao.RANKEAR]
    if len(rankings) <= 1:
        return specs

    dominante = max(rankings, key=lambda s: scores_por_dominio.get(s.dominio, 0.0)).dominio

    mantidos: list[QuerySpec] = []
    for spec in specs:
        if spec.operacao != Operacao.RANKEAR:
            mantidos.append(spec)
            continue
        if spec.dominio == dominante:
            mantidos.append(spec)
            continue
        palavras = _RANKING_KEYWORDS.get(spec.dominio, ())
        if any(palavra in tokens for palavra in palavras):
            mantidos.append(spec)
    return mantidos


def _extrair_contexto_espacial(
    grupo: GrupoSemantico,
    rotulo: str,
) -> Optional[ContextoEspacial]:
    cat = next((c for c in grupo.categorias if c.rotulo == rotulo), None)
    if cat is None:
        return None

    dentro_de_str = cat.query_spec.get("contexto_espacial", {}).get("dentro_de")
    if not dentro_de_str:
        return None

    try:
        return ContextoEspacial(dentro_de=Dominio(dentro_de_str))
    except ValueError:
        return None


async def entender(
    texto: TextoProcessado,
) -> PlanoConsulta:
    if not is_ready():
        await warm_up()

    if _RE_FORA_SP.search(texto.normalizado):
        return PlanoConsulta(specs=[], confianca=1.0, fora_escopo=True)

    vetor = embed_texto(texto.corrigido)
    texto.embedding = vetor.tolist()

    specs: list[QuerySpec] = []
    scores_por_dominio: dict[Dominio, float] = {}
    melhor_score_geral = 0.0
    contexto_espacial_ativado: Optional[ContextoEspacial] = None

    for grupo in GRUPOS:
        rotulo, score = _classificar_grupo(vetor, grupo)
        if rotulo is None:
            continue

        melhor_score_geral = max(melhor_score_geral, score)

        if grupo.nome == "contexto_espacial":
            if _RE_CONTEXTO_ESPACIAL.search(texto.normalizado):
                contexto_espacial_ativado = _extrair_contexto_espacial(grupo, rotulo)
            continue

        if grupo.nome == "operacao_especial":
            if rotulo == "sobrepor":
                specs = [s.model_copy(update={"operacao": Operacao.SOBREPOR}) for s in specs]
            continue

        spec = _cat_para_spec(grupo, rotulo)
        if spec is not None:
            specs.append(spec)
            scores_por_dominio[spec.dominio] = score

    specs = _aplicar_margem_dominante(specs, scores_por_dominio)
    melhor_score_geral = _boost_specs(texto.tokens, vetor, specs, scores_por_dominio, melhor_score_geral)

    tokens_set = set(texto.tokens)
    specs = _filtrar_rankings(specs, scores_por_dominio, tokens_set)
    specs = _colapsar_sobreposicao_imovel(specs, tokens_set)

    if _RE_CAR.search(texto.normalizado):
        specs = _specs_para_car(texto.normalizado)
        return PlanoConsulta(specs=specs, confianca=1.0, fora_escopo=False)

    if contexto_espacial_ativado and contexto_espacial_ativado.dentro_de:
        dominio_filtro = contexto_espacial_ativado.dentro_de
        specs = [s for s in specs if s.dominio != dominio_filtro]
        specs = [s.model_copy(update={"contexto_espacial": contexto_espacial_ativado}) for s in specs]

    if not specs or melhor_score_geral < CONFIDENCE_THRESHOLD:
        return PlanoConsulta(specs=[], confianca=melhor_score_geral, fora_escopo=False)

    confianca = _agregar_confianca(specs, scores_por_dominio, melhor_score_geral)
    return PlanoConsulta(specs=specs, confianca=confianca, fora_escopo=False)
