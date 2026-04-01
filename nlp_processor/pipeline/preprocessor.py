# -*- coding: utf-8 -*-
"""
Pré-processamento de texto para o pipeline NLP ambiental.
"""
from __future__ import annotations

import re
import unicodedata


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
