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
BINARIZER_PATH = MODELS_DIR / "binarizer.joblib"

_PREPROCESSOR_INSTANCE = AdvancedGeoASGPreprocessor()

VALID_INTENTS = {
    "buscar_queimadas", "buscar_desmatamentos", "buscar_unidades_conservacao",
    "buscar_terras_indigenas", "buscar_assentamentos", "buscar_quilombolas",
    "buscar_imoveis_rurais", "buscar_imoveis_queimada", "buscar_imoveis_desmatamento",
    "buscar_imoveis_quilombo", "buscar_imoveis_ti", "buscar_camadas_estaduais",
    "buscar_imoveis_em_camadas", "buscar_passivos_imovel", "buscar_focos_queimada_imovel",
    "buscar_documentos", "buscar_maiores_quantidades",
}

class IntentClassifier:

    def __init__(self, confidence_threshold: float = 0.50) -> None:
        self._vectorizer = None
        self._classifier = None
        self._binarizer = None
        self._confidence_threshold = confidence_threshold

    def _ensure_loaded(self) -> None:
        if self._classifier is None or self._vectorizer is None or self._binarizer is None:
            if not VECTORIZER_PATH.exists() or not CLASSIFIER_PATH.exists() or not BINARIZER_PATH.exists():
                raise FileNotFoundError("Modelos não encontrados. Execute o treino primeiro.")
            logger.info("Carregando modelos de classificação de intenção do disco...")
            self._vectorizer = joblib.load(VECTORIZER_PATH)
            self._classifier = joblib.load(CLASSIFIER_PATH)
            self._binarizer = joblib.load(BINARIZER_PATH)
            logger.info("Modelos carregados com sucesso.")

    def predict_multiple(self, text: Union[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
        # Removido self._ensure_loaded() daqui para evitar I/O síncrono por requisição
        model_text = self._extract_text(text)
        if not model_text or not str(model_text).strip():
            return [("fora_escopo", 0.0)]

        X = self._vectorizer.transform([model_text])
        
        # predict_proba no MultiOutput devolve uma lista de arrays (um por intenção)
        probabilities_list = self._classifier.predict_proba(X)
        classes = self._binarizer.classes_

        detected_intents: List[Tuple[str, float]] = []
        
        for idx, intent_class in enumerate(classes):
            intent_str = str(intent_class)
            
            # Garante que a estrutura da lista de probabilidades está correta antes de acessar
            if len(probabilities_list) > idx and len(probabilities_list[idx]) > 0 and len(probabilities_list[idx][0]) > 1:
                prob_active = float(probabilities_list[idx][0][1])
            else:
                prob_active = 0.0
            
            if prob_active >= self._confidence_threshold and intent_str in VALID_INTENTS:
                detected_intents.append((intent_str, round(prob_active, 4)))

        # Fallback de segurança se nenhuma intenção passar do limiar (threshold)
        if not detected_intents:
            try:
                probs_fallback = [float(p[0][1]) for p in probabilities_list if len(p) > 0 and len(p[0]) > 1]
                if probs_fallback:
                    max_idx = np.argmax(probs_fallback)
                    return [(str(classes[max_idx]), round(probs_fallback[max_idx], 4))]
            except Exception as e:
                logger.error("Erro ao gerar fallback de intenções: %s", e)
            
            return [("fora_escopo", 0.0)]

        return sorted(detected_intents, key=lambda x: x[1], reverse=True)

    def _extract_text(self, text: Union[str, Dict[str, Any]]) -> str:
        if isinstance(text, dict):
            return text.get("text_for_entities_and_rag", "")
        
        nlp_result = _PREPROCESSOR_INSTANCE.process(text)
        return nlp_result["text_for_entities_and_rag"]

    def is_ready(self) -> bool:
        return self._classifier is not None and self._vectorizer is not None and self._binarizer is not None


_classifier_instance = None

def get_classifier() -> IntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
        try:
            # O modelo agora é carregado uma única vez na inicialização global
            _classifier_instance._ensure_loaded()
        except Exception as e:
            logger.error("Falha crítica ao carregar o IntentClassifier: %s", e)
    return _classifier_instance