# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum

LIMIAR_DOMINIO_CONCRETO = 0.55
LIMIAR_DOMINIO_AREA = 0.58
LIMIAR_ESPECIALIZADO = 0.62
LIMIAR_AUXILIAR = 0.62
LIMIAR_FALLBACK = LIMIAR_DOMINIO_CONCRETO

_PISO_UTIL = 0.45
_TETO_UTIL = 0.80


class FaixaConfianca(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


def calibrar(score_bruto: float) -> float:
    if score_bruto <= _PISO_UTIL:
        return 0.0
    if score_bruto >= _TETO_UTIL:
        return 1.0
    return round((score_bruto - _PISO_UTIL) / (_TETO_UTIL - _PISO_UTIL), 3)


def faixa(score_calibrado: float) -> FaixaConfianca:
    if score_calibrado >= 0.66:
        return FaixaConfianca.ALTA
    if score_calibrado >= 0.33:
        return FaixaConfianca.MEDIA
    return FaixaConfianca.BAIXA
