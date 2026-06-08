# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
}


class IntentClassifier:

    def __init__(self, confidence_threshold: float = 0.35) -> None:
        self._vectorizer = None
        self._classifier = None
        self._loaded = False
        self._confidence_threshold = confidence_threshold

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

    def predict_multiple(self, text: Union[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
        self._ensure_loaded()
        
        model_text = self._extract_text(text)
        if not model_text or not str(model_text).strip():
            return [("fora_escopo", 0.0)]

        X = self._vectorizer.transform([model_text])
        probabilities = self._classifier.predict_proba(X)[0]
        classes = self._classifier.classes_

        detected_intents: List[Tuple[str, float]] = []
        
        for intent_class, prob in zip(classes, probabilities):
            intent_str = str(intent_class)
            if prob >= self._confidence_threshold and intent_str in VALID_INTENTS:
                detected_intents.append((intent_str, round(float(prob), 4)))

        if not detected_intents:
            max_idx = np.argmax(probabilities)
            return [(str(classes[max_idx]), round(float(probabilities[max_idx]), 4))]

        return sorted(detected_intents, key=lambda x: x[1], reverse=True)

    def _extract_text(self, text: Union[str, Dict[str, Any]]) -> str:
        if isinstance(text, dict):
            return text.get("text_for_entities_and_rag", "")
        
        nlp_result = _PREPROCESSOR_INSTANCE.process(text)
        return nlp_result["text_for_classifier"]

    def is_ready(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except FileNotFoundError:
            return False


_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance