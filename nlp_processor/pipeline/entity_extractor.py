# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_model import Municipio, RegiaoAdministrativa
from nlp_processor.domain.contracts import (
    FiltrosConsulta,
    LocalConsulta,
    PeriodoConsulta,
    PlanoConsulta,
    QuerySpec,
    TextoProcessado,
)
from nlp_processor.domain.enums import Operacao
from nlp_processor.infrastructure import gazetteer

_RE_CAR = re.compile(r"\b[A-Z]{2}-\d{7}-[A-Z0-9]{32}\b", re.IGNORECASE)
_RE_ANO = re.compile(r"\b(20\d{2})\b")
_RE_DATA_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

_RANKING_DEFAULT = 5
_RANKING_TOP_DEFAULT = 3
_RANKING_MAX = 50

_RE_TOP_N = re.compile(r"\btop\s*(\d{1,3})\b")
_RE_N_QUALIFICADO = re.compile(
    r"\b(\d{1,3})\s+(?:maiores|primeiros|principais|municipios|cidades)\b"
)
_RE_OS_N = re.compile(r"\b(?:os|as)\s+(\d{1,3})\b")
_RE_SINGULAR = re.compile(
    r"\b(qual\s+(?:o\s+|a\s+)?(?:municipio|cidade)|"
    r"o\s+municipio\s+que|a\s+cidade\s+que|maior\s+numero|"
    r"qual\s+(?:o\s+|a\s+)?(?:teve|tem)\s+mais)\b"
)

_NUMEROS_EXTENSO = {
    "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10,
}

_BIOMAS = {"cerrado", "mata atlantica", "mata atlântica", "amazonia", "amazônia", "pantanal", "caatinga", "pampa"}
_SENSORES = {"aqua", "terra", "goes", "viirs", "modis"}
_FASES_TI = {"homologada", "declarada", "delimitada", "encaminhada", "em estudo"}

_PERIODOS_RELATIVOS = {
    "ultimo mes": 30,
    "últimos 30 dias": 30,
    "últimos 3 meses": 90,
    "últimos 6 meses": 180,
    "este ano": None,
    "ano passado": None,
    "último ano": 365,
}


def _extrair_car(texto_normalizado: str) -> Optional[str]:
    match = _RE_CAR.search(texto_normalizado)
    return match.group(0).upper() if match else None


def _extrair_periodo(texto_normalizado: str) -> Optional[PeriodoConsulta]:
    match_iso = _RE_DATA_ISO.findall(texto_normalizado)
    if len(match_iso) >= 2:
        return PeriodoConsulta(data_inicio=match_iso[0], data_fim=match_iso[1])
    if len(match_iso) == 1:
        return PeriodoConsulta(data_inicio=match_iso[0])

    hoje = date.today()
    if "este ano" in texto_normalizado or "esse ano" in texto_normalizado:
        return PeriodoConsulta(
            data_inicio=f"{hoje.year}-01-01",
            data_fim=hoje.isoformat(),
        )
    if "ano passado" in texto_normalizado:
        return PeriodoConsulta(
            data_inicio=f"{hoje.year - 1}-01-01",
            data_fim=f"{hoje.year - 1}-12-31",
        )

    for frase, dias in _PERIODOS_RELATIVOS.items():
        if frase in texto_normalizado and dias:
            inicio = hoje - timedelta(days=dias)
            return PeriodoConsulta(data_inicio=inicio.isoformat(), data_fim=hoje.isoformat())

    anos = _RE_ANO.findall(texto_normalizado)
    if anos:
        ano = anos[-1]
        return PeriodoConsulta(data_inicio=f"{ano}-01-01", data_fim=f"{ano}-12-31")

    return None


def _extrair_bioma(tokens: list[str]) -> Optional[str]:
    texto = " ".join(tokens)
    for bioma in _BIOMAS:
        if bioma in texto:
            return bioma
    return None


def _extrair_sensor(tokens: list[str]) -> Optional[str]:
    for token in tokens:
        if token.lower() in _SENSORES:
            return token.upper()
    return None


def _extrair_fase_ti(texto_normalizado: str) -> Optional[str]:
    for fase in _FASES_TI:
        if fase in texto_normalizado:
            return fase
    return None


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


async def _resolver_local(
    session: AsyncSession,
    texto_normalizado: str,
    municipio_contexto: Optional[str],
) -> LocalConsulta:
    codigo_car = _extrair_car(texto_normalizado)
    if codigo_car:
        return LocalConsulta(codigo_car=codigo_car)

    chave_municipio = gazetteer.encontrar_municipio(texto_normalizado)
    if not chave_municipio and municipio_contexto:
        chave_municipio = _normalizar(municipio_contexto)

    chave_regiao = gazetteer.encontrar_regiao(texto_normalizado)

    if chave_regiao and (not chave_municipio or len(chave_regiao) > len(chave_municipio)):
        local = await _resolver_regiao(session, chave_regiao)
        if local:
            return local

    if chave_municipio:
        local = await _resolver_municipio(session, chave_municipio)
        if local:
            return local

    return LocalConsulta()


async def _resolver_municipio(session: AsyncSession, chave: str) -> Optional[LocalConsulta]:
    stmt = select(Municipio.id, Municipio.nome).where(
        Municipio.nome_normalizado == chave
    ).limit(1)
    row = (await session.execute(stmt)).first()
    if not row:
        return None
    return LocalConsulta(municipio_nome=row.nome, municipio_id=row.id)


async def _resolver_regiao(session: AsyncSession, chave: str) -> Optional[LocalConsulta]:
    stmt = select(RegiaoAdministrativa.id, RegiaoAdministrativa.nome).where(
        RegiaoAdministrativa.nome_normalizado == chave
    ).limit(1)
    row = (await session.execute(stmt)).first()
    if not row:
        return None
    return LocalConsulta(
        regiao_administrativa_nome=row.nome,
        regiao_administrativa_id=row.id,
    )


def _extrair_quantidade_ranking(texto_normalizado: str) -> int:
    for regex in (_RE_TOP_N, _RE_N_QUALIFICADO, _RE_OS_N):
        match = regex.search(texto_normalizado)
        if match:
            return max(1, min(int(match.group(1)), _RANKING_MAX))

    for palavra, valor in _NUMEROS_EXTENSO.items():
        if re.search(rf"\b{palavra}\s+(?:maiores|primeiros|principais|municipios|cidades)\b", texto_normalizado):
            return valor

    if _RE_SINGULAR.search(texto_normalizado):
        return 1
    if "top" in texto_normalizado:
        return _RANKING_TOP_DEFAULT
    return _RANKING_DEFAULT


def _extrair_filtros(spec: QuerySpec, texto_normalizado: str, tokens: list[str]) -> FiltrosConsulta:
    filtros = spec.filtros.model_copy()
    filtros = filtros.model_copy(update={
        "bioma": _extrair_bioma(tokens),
        "sensor": _extrair_sensor(tokens),
        "fase_ti": _extrair_fase_ti(texto_normalizado),
    })
    if spec.operacao == Operacao.RANKEAR:
        filtros = filtros.model_copy(update={"limite": _extrair_quantidade_ranking(texto_normalizado)})
    return filtros


async def extrair_e_validar(
    session: AsyncSession,
    plano: PlanoConsulta,
    texto: TextoProcessado,
    municipio_contexto: Optional[str] = None,
) -> list[QuerySpec]:
    local = await _resolver_local(session, texto.normalizado, municipio_contexto)
    periodo = _extrair_periodo(texto.normalizado)

    specs_preenchidos: list[QuerySpec] = []
    for spec in plano.specs:
        filtros = _extrair_filtros(spec, texto.normalizado, texto.tokens)
        specs_preenchidos.append(
            spec.model_copy(update={
                "onde": local,
                "periodo": periodo,
                "filtros": filtros,
            })
        )

    return specs_preenchidos
