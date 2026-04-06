# -*- coding: utf-8 -*-
"""
Script de treinamento do classificador de intenções.

Execução:
    python -m nlp_processor.training.train

O script:
  1. Carrega os exemplos de nlp_processor/training/train_data.py
  2. Aplica normalização de texto
  3. Vetoriza com TF-IDF (n-gramas 1-2)
  4. Treina Logistic Regression com validação cruzada
  5. Salva os artefatos em nlp_processor/models/
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

from nlp_processor.pipeline.preprocessor import normalizar
from nlp_processor.training.train_data import TRAIN_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"


def _preparar_dados() -> tuple[list[str], list[str]]:
    textos = [normalizar(t) for t, _ in TRAIN_DATA]
    rotulos = [r for _, r in TRAIN_DATA]
    return textos, rotulos


def treinar() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    textos, rotulos = _preparar_dados()

    logger.info("Total de exemplos: %d", len(textos))
    logger.info("Intenções detectadas: %s", sorted(set(rotulos)))

    # Pipeline: TF-IDF por palavra + TF-IDF por trigrama de caractere (melhor generalização)
    # + LogReg com regularização mais forte (C baixo) para evitar overfitting
    word_vec = TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        min_df=1,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    char_vec = TfidfVectorizer(
        ngram_range=(3, 4),
        analyzer="char_wb",
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    features = FeatureUnion([("word", word_vec), ("char", char_vec)])
    classifier = LogisticRegression(
        max_iter=1000,
        C=0.5,          # regularização mais forte — reduz overfitting
        class_weight="balanced",
        solver="lbfgs",
    )

    # Validação cruzada (5-fold estratificado)
    pipeline = Pipeline([("features", features), ("clf", classifier)])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, textos, rotulos, cv=cv, scoring="f1_macro")
    logger.info("F1-macro (CV 5-fold): %.3f ± %.3f", scores.mean(), scores.std())

    if scores.mean() < 0.70:
        logger.warning(
            "F1-macro abaixo de 0.70 (%.3f). "
            "Adicione mais exemplos de treinamento em train_data.py.",
            scores.mean(),
        )

    # Treino final no corpus completo
    X = features.fit_transform(textos)
    classifier.fit(X, rotulos)

    # Relatório final (treino — serve para detectar classes problemáticas)
    preds = classifier.predict(X)
    logger.info("\n%s", classification_report(rotulos, preds, target_names=sorted(set(rotulos))))

    # Salva pipeline completo (features + classifier) em dois artefatos
    # para manter compatibilidade com IntentClassifier.predict()
    joblib.dump(features, VECTORIZER_PATH)
    joblib.dump(classifier, CLASSIFIER_PATH)
    logger.info("Artefatos salvos em: %s", MODELS_DIR)


if __name__ == "__main__":
    treinar()
