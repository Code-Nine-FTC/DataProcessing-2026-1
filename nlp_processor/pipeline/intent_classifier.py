# -*- coding: utf-8 -*-
"""
Classificador de intenções via TF-IDF + Logistic Regression.
O modelo é treinado via nlp_processor/training/train.py e carregado em memória.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from nlp_processor.pipeline.preprocessor import normalizar

logger = logging.getLogger(__name__)

# Diretório onde os artefatos treinados são salvos
MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"

# Intenções reconhecidas pelo sistema
INTENCOES = [
    "buscar_queimadas",
    "buscar_desmatamentos",
    "buscar_unidades_conservacao",
    "buscar_terras_indigenas",
    "buscar_assentamentos",
    "buscar_quilombolas",
    "buscar_imoveis_rurais",
    "buscar_documentos",
    "fora_escopo",
]


class IntentClassifier:
    """
    Wrapper thread-safe do classificador treinado.
    Carrega os artefatos do disco uma única vez.
    """

    def __init__(self) -> None:
        self._vectorizer = None
        self._classifier = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not VECTORIZER_PATH.exists() or not CLASSIFIER_PATH.exists():
            raise FileNotFoundError(
                f"Modelos de classificação não encontrados em {MODELS_DIR}. "
                "Execute `python -m nlp_processor.training.train` primeiro."
            )
        self._vectorizer = joblib.load(VECTORIZER_PATH)
        self._classifier = joblib.load(CLASSIFIER_PATH)
        self._loaded = True
        logger.info("Classificador de intenções carregado.")

    def predict(self, texto: str) -> tuple[str, float]:
        """
        Retorna (intenção, confiança) para o texto fornecido.
        """
        self._ensure_loaded()
        normalizado = normalizar(texto)
        X = self._vectorizer.transform([normalizado])
        intencao = self._classifier.predict(X)[0]
        proba = np.max(self._classifier.predict_proba(X))
        return intencao, float(proba)

    def is_ready(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except FileNotFoundError:
            return False


# Singleton
_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
