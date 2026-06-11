# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from spellchecker import SpellChecker

from nlp_processor.domain.contracts import TextoProcessado

_STOPWORDS = {
    "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "para", "por", "com", "sem", "sob", "sobre", "entre", "até",
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "e", "ou", "que", "se", "não", "mais", "menos", "já",
    "me", "te", "se", "nos", "vos", "lhe", "lhes",
    "qual", "quais", "quando", "onde", "como", "quanto",
}

_PESO_DOMINIO = 50_000_000
_VOCAB_DOMINIO = [
    "desmatamento", "desmatamentos", "desmatada", "desmatadas",
    "queimada", "queimadas", "incendio", "incendios", "fogo", "foco", "focos",
    "quilombola", "quilombolas", "quilombo", "quilombos",
    "assentamento", "assentamentos",
    "imovel", "imoveis", "fazenda", "propriedade",
    "indigena", "indigenas", "reserva", "conservacao", "unidade", "unidades",
    "bioma", "cerrado", "caatinga", "amazonia",
    "prodes", "deter", "ibama", "incra", "itesp", "sigef",
    "ranking", "rankings", "municipio", "municipios", "top", "car",
]

_spell = SpellChecker(language="pt")
_spell.word_frequency.load_json({palavra: _PESO_DOMINIO for palavra in _VOCAB_DOMINIO})
_RE_ESPACOS = re.compile(r"\s+")
_RE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")

_SIGLAS = {
    "sp": "são paulo",
    "ti": "terra indígena",
    "tis": "terras indígenas",
    "uc": "unidade de conservação",
    "ucs": "unidades de conservação",
    "apa": "área de proteção ambiental",
    "rppn": "reserva particular do patrimônio natural",
}


def registrar_nomes_proprios(tokens: Iterable[str]) -> None:
    conhecidos = [t for t in tokens if t and t.isalpha()]
    if conhecidos:
        _spell.word_frequency.load_words(conhecidos)


def _expandir_siglas(texto: str) -> str:
    expandidos = [
        _SIGLAS.get(palavra.lower(), palavra) if palavra.isalpha() else palavra
        for palavra in texto.split()
    ]
    return " ".join(expandidos)


def _higienizar(texto: str) -> str:
    texto = _RE_CONTROLE.sub(" ", texto)
    return _RE_ESPACOS.sub(" ", texto).strip()


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


def _corrigir(texto: str) -> str:
    palavras = texto.lower().split()
    erradas = _spell.unknown(palavras)
    corrigidas = []
    for palavra in palavras:
        if palavra in erradas:
            sugestao = _spell.correction(palavra)
            corrigidas.append(sugestao if sugestao else palavra)
        else:
            corrigidas.append(palavra)
    return " ".join(corrigidas)


def _tokenizar(texto: str) -> list[str]:
    return [t for t in texto.split() if t not in _STOPWORDS and len(t) > 1]


def processar(texto_bruto: str) -> TextoProcessado:
    higienizado = _higienizar(texto_bruto)
    expandido = _expandir_siglas(higienizado)
    corrigido = _corrigir(expandido)
    normalizado = _normalizar(corrigido)
    tokens = _tokenizar(normalizado)

    return TextoProcessado(
        original=texto_bruto,
        normalizado=normalizado,
        corrigido=corrigido,
        tokens=tokens,
    )
