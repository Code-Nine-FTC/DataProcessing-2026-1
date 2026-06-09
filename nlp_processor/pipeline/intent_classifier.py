# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Union

import joblib
import numpy as np

from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"

_PREPROCESSOR_INSTANCE = AdvancedGeoASGPreprocessor()

VALID_INTENTS = {
    "buscar_queimadas",
    "buscar_desmatamentos",
    "buscar_unidades_conservacao",
    "buscar_terras_indigenas",
    "buscar_assentamentos",
    "buscar_quilombolas",
    "buscar_imoveis_rurais",
    "buscar_imoveis_queimada",
    "buscar_imoveis_desmatamento",
    "buscar_imoveis_quilombo",
    "buscar_imoveis_ti",
    "buscar_camadas_estaduais",
    "buscar_imoveis_em_camadas",
    "buscar_passivos_imovel",
    "buscar_focos_queimada_imovel",
    "buscar_documentos",
    "buscar_maiores_quantidades",
    "fora_escopo",
}


class IntentClassifier:

    def __init__(self, confidence_threshold: float = 0.30) -> None:
        self._vectorizer = None
        self._classifier = None
        self._confidence_threshold = confidence_threshold

    def _ensure_loaded(self) -> None:
        if self._classifier is None or self._vectorizer is None:
            if not VECTORIZER_PATH.exists() or not CLASSIFIER_PATH.exists():
                raise FileNotFoundError("Modelos não encontrados. Execute o treino primeiro.")
            logger.info("Carregando modelos de classificação de intenção do disco...")
            self._vectorizer = joblib.load(VECTORIZER_PATH)
            self._classifier = joblib.load(CLASSIFIER_PATH)
            logger.info("Modelos carregados com sucesso.")

    def predict(self, text: Union[str, Dict[str, Any]]) -> tuple[str, float]:
        """Retorna (intent, confidence) para o texto de entrada."""
        model_text = self._extract_text(text)
        if not model_text or not str(model_text).strip():
            return "fora_escopo", 0.0

        X = self._vectorizer.transform([model_text])
        probabilities = self._classifier.predict_proba(X)[0]
        classes = self._classifier.classes_

        best_idx = int(np.argmax(probabilities))
        best_intent = str(classes[best_idx])
        best_confidence = float(probabilities[best_idx])

        if best_intent not in VALID_INTENTS:
            logger.warning("Intent inválido retornado pelo modelo: %s", best_intent)
            return "fora_escopo", 0.0

        return best_intent, round(best_confidence, 4)

    def _extract_text(self, text: Union[str, Dict[str, Any]]) -> str:
        if isinstance(text, dict):
            return text.get("text_for_entities_and_rag", "")
        nlp_result = _PREPROCESSOR_INSTANCE.process(text)
        return nlp_result["text_for_entities_and_rag"]

    def is_ready(self) -> bool:
        return self._classifier is not None and self._vectorizer is not None


_classifier_instance: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
        try:
            _classifier_instance._ensure_loaded()
        except Exception as e:
            logger.error("Falha crítica ao carregar o IntentClassifier: %s", e)
    return _classifier_instance
