# -*- coding: utf-8 -*-
"""
Pré-processamento de texto para o pipeline NLP ambiental.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)


def normalizar(texto: str) -> str:
    """
    Normaliza texto: lowercase, remove acentos e pontuação excessiva,
    colapsa espaços.
    """
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s\-/]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def tokenizar(texto: str) -> list[str]:
    return normalizar(texto).split()


# ---------------------------------------------------------------------------
# Correção ortográfica (pyspellchecker)
# ---------------------------------------------------------------------------
# Aplicada à PERGUNTA do usuário (não ao matching contra o banco), para tolerar
# erros de digitação antes da classificação de intenção e extração de entidades.
#
# Cuidados:
#   - distância 1 apenas (corrige só typos óbvios; evita trocas absurdas como
#     "ranking" -> "rafting" ou "ubatuba" -> "batuta");
#   - jargão de domínio é protegido — o dicionário PT genérico não conhece
#     termos como "desmatamento"/"ranking" e os "corrigiria" para algo errado;
#   - nomes de municípios (passados em `protegidos`) são preservados;
#   - números, datas e códigos (CAR) não são tocados (só palavras 100% alfabéticas
#     delimitadas por fronteira de palavra são candidatas).

# Vocabulário de domínio (forma normalizada, sem acento) que NÃO deve ser corrigido.
_TERMOS_DOMINIO = {
    # ranking / agregação
    "ranking", "rank", "top",
    # queimadas
    "queimada", "queimadas", "foco", "focos", "incendio", "incendios", "fogo",
    # desmatamento
    "desmatamento", "desmatamentos", "desmatado", "desmatada", "supressao",
    "prodes", "deter",
    # imóveis / CAR
    "car", "sicar", "imovel", "imoveis", "propriedade", "propriedades",
    "fazenda", "fazendas", "sitio", "sitios", "rural", "rurais",
    # áreas protegidas / especiais
    "uc", "ucs", "apa", "apas", "resex", "rebio", "flona", "rppn", "snuc",
    "cnuc", "quilombo", "quilombos", "quilombola", "quilombolas", "indigena",
    "indigenas", "assentamento", "assentamentos", "bacia", "bacias", "bioma",
    # geográfico / técnico
    "geojson", "bbox", "geom", "geometria", "centroid", "camada", "camadas",
    # sensores / fontes
    "viirs", "modis", "aqua", "goes", "npp", "noaa", "msg", "inpe", "ibge",
    # siglas de estado / região
    "sp", "br", "rmsp", "rmbs", "rmc", "rmrp", "rmvp",
}

# Apenas palavras alfabéticas (com acento) de 4+ letras, delimitadas — assim
# trechos colados a dígitos (códigos CAR, datas) nunca são candidatos.
_PALAVRA_RE = re.compile(r"\b[^\W\d_]{4,}\b", re.UNICODE)

_spell = None
_spell_carregado = False


def _carregar_spell():
    """Carrega o SpellChecker PT uma única vez. Falha de forma silenciosa
    (correção vira no-op) se a lib não estiver instalada."""
    global _spell, _spell_carregado
    if _spell_carregado:
        return _spell
    _spell_carregado = True
    try:
        from spellchecker import SpellChecker

        _spell = SpellChecker(language="pt", distance=1)
        # Ensina o jargão de domínio ao corretor com frequência alta. Assim esses
        # termos (ausentes do dicionário PT genérico) viram ALVO de correção —
        # "desmatameto" -> "desmatamento", "queimda" -> "queimada", "rankng" ->
        # "ranking" — e vencem o desempate de candidatos por frequência.
        for termo in _TERMOS_DOMINIO:
            _spell.word_frequency.add(termo, 5_000_000)
        logger.info("SpellChecker (pt, distance=1) carregado com vocabulário de domínio.")
    except Exception as exc:  # pragma: no cover - depende do ambiente
        _spell = None
        logger.warning(
            "pyspellchecker indisponível (%s); correção ortográfica desativada.", exc
        )
    return _spell


def _norm_token(palavra: str) -> str:
    base = unicodedata.normalize("NFD", palavra.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def corrigir_ortografia(texto: str, protegidos: Optional[set[str]] = None) -> str:
    """Corrige erros de digitação óbvios (distância 1) na pergunta do usuário.

    Preserva nomes próprios (municípios em `protegidos`, em forma normalizada),
    jargão de domínio, siglas, números e códigos. Se a lib não estiver
    instalada, devolve o texto original inalterado.
    """
    spell = _carregar_spell()
    if spell is None or not texto:
        return texto

    protegidos = protegidos or set()

    def _corrige(match: "re.Match[str]") -> str:
        palavra = match.group(0)
        baixa = palavra.lower()
        norm = _norm_token(baixa)
        if norm in _TERMOS_DOMINIO or norm in protegidos:
            return palavra
        if baixa in spell:  # já é palavra conhecida do dicionário
            return palavra
        correcao = spell.correction(baixa)
        if not correcao or correcao == baixa:
            return palavra
        if palavra[:1].isupper():
            correcao = correcao.capitalize()
        return correcao

    return _PALAVRA_RE.sub(_corrige, texto)
