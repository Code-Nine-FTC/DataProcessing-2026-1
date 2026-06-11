# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_model import Municipio, RegiaoAdministrativa

logger = logging.getLogger(__name__)

try:
    import ahocorasick
    _HAS_AHOCORASICK = True
except ImportError:
    _HAS_AHOCORASICK = False
    logger.warning("pyahocorasick não instalado — gazetteer em busca linear.")

_CAPITAL_AMBIGUA = "sao paulo"
_MARCADORES_MUNICIPAIS = (
    "municipio de sao paulo",
    "municipio sao paulo",
    "cidade de sao paulo",
    "capital paulista",
    "capital do estado",
)

_aut_municipios: object | None = None
_aut_regioes: object | None = None
_municipios: set[str] = set()
_regioes: set[str] = set()
_tokens_proprios: set[str] = set()


async def warm_up(session: AsyncSession) -> None:
    global _aut_municipios, _aut_regioes, _municipios, _regioes, _tokens_proprios

    rows_mun = (await session.execute(select(Municipio.nome, Municipio.nome_normalizado))).all()
    _municipios = {row.nome_normalizado.lower() for row in rows_mun if row.nome_normalizado}

    rows_ra = (await session.execute(
        select(RegiaoAdministrativa.nome, RegiaoAdministrativa.nome_normalizado)
    )).all()
    _regioes = {row.nome_normalizado.lower() for row in rows_ra if row.nome_normalizado}

    _tokens_proprios = set()
    for row in rows_mun:
        _tokens_proprios.update(row.nome.lower().split())
    for row in rows_ra:
        _tokens_proprios.update(row.nome.lower().split())

    if _HAS_AHOCORASICK:
        _aut_municipios = _construir_automaton(_municipios)
        _aut_regioes = _construir_automaton(_regioes)

    logger.info("Gazetteer aquecido: %d municípios, %d regiões.", len(_municipios), len(_regioes))


def is_ready() -> bool:
    return bool(_municipios)


def vocabulario_tokens() -> set[str]:
    return set(_tokens_proprios)


def encontrar_municipio(texto_normalizado: str) -> Optional[str]:
    candidatos = _matches(_aut_municipios, _municipios, texto_normalizado)
    candidatos.sort(key=len, reverse=True)
    for chave in candidatos:
        if chave == _CAPITAL_AMBIGUA and not _tem_marcador_municipal(texto_normalizado):
            continue
        return chave
    return None


def encontrar_regiao(texto_normalizado: str) -> Optional[str]:
    candidatos = _matches(_aut_regioes, _regioes, texto_normalizado)
    if not candidatos:
        return None
    candidatos.sort(key=len, reverse=True)
    return candidatos[0]


def _construir_automaton(chaves: set[str]) -> object:
    automaton = ahocorasick.Automaton()
    for chave in chaves:
        automaton.add_word(chave, chave)
    automaton.make_automaton()
    return automaton


def _matches(automaton: object | None, chaves: set[str], texto: str) -> list[str]:
    if automaton is None:
        return _matches_linear(chaves, texto)

    fim_texto = len(texto)
    encontrados: list[str] = []
    for fim, chave in automaton.iter(texto):
        inicio = fim - len(chave) + 1
        if _delimitado(texto, inicio, fim, fim_texto):
            encontrados.append(chave)
    return encontrados


def _matches_linear(chaves: set[str], texto: str) -> list[str]:
    fim_texto = len(texto)
    encontrados: list[str] = []
    for chave in chaves:
        inicio = texto.find(chave)
        while inicio != -1:
            fim = inicio + len(chave) - 1
            if _delimitado(texto, inicio, fim, fim_texto):
                encontrados.append(chave)
                break
            inicio = texto.find(chave, inicio + 1)
    return encontrados


def _delimitado(texto: str, inicio: int, fim: int, fim_texto: int) -> bool:
    antes_livre = inicio == 0 or not texto[inicio - 1].isalnum()
    depois_livre = fim == fim_texto - 1 or not texto[fim + 1].isalnum()
    return antes_livre and depois_livre


def _tem_marcador_municipal(texto: str) -> bool:
    return any(marcador in texto for marcador in _MARCADORES_MUNICIPAIS)
