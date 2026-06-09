# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import FeatureUnion

from nlp_processor.training.train_data import TRAIN_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"

MIN_F1_THRESHOLD = 0.70

_preprocessor = None


def _get_preprocessor():
    global _preprocessor
    if _preprocessor is None:
        from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor
        _preprocessor = AdvancedGeoASGPreprocessor()
    return _preprocessor


def _preprocess(text: str) -> str:
    return _get_preprocessor().process(text)["text_for_entities_and_rag"]


def _load_training_data() -> tuple[list[str], list[str]]:
    texts = [_preprocess(text) for text, _ in TRAIN_DATA]
    labels = [label for _, label in TRAIN_DATA]
    return texts, labels


def _build_feature_extractor() -> FeatureUnion:
    word_vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    return FeatureUnion([("word", word_vectorizer)])


def _cross_validate(texts: list[str], labels: list[str], n_splits: int = 5) -> float:
    """Avalia F1-macro com StratifiedKFold para garantir distribuição balanceada."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    f1_scores: list[float] = []

    for fold, (train_idx, test_idx) in enumerate(skf.split(texts, labels), 1):
        texts_train = [texts[i] for i in train_idx]
        texts_test = [texts[i] for i in test_idx]
        labels_train = [labels[i] for i in train_idx]
        labels_test = [labels[i] for i in test_idx]

        feat = _build_feature_extractor()
        X_train = feat.fit_transform(texts_train)
        X_test = feat.transform(texts_test)

        clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
        clf.fit(X_train, labels_train)

        preds = clf.predict(X_test)
        f1 = f1_score(labels_test, preds, average="macro", zero_division=0)
        f1_scores.append(f1)
        logger.info("  Fold %d — F1-macro: %.3f", fold, f1)

    mean, std = float(np.mean(f1_scores)), float(np.std(f1_scores))
    logger.info("CV %d-fold — F1-macro: %.3f ± %.3f", n_splits, mean, std)
    return mean


def _fit_and_save(
    features: FeatureUnion,
    classifier: LogisticRegression,
    texts: list[str],
    labels: list[str],
) -> None:
    texts_train, texts_test, labels_train, labels_test = train_test_split(
        texts, labels, test_size=0.20, random_state=42, stratify=labels
    )

    X_train = features.fit_transform(texts_train)
    X_test = features.transform(texts_test)

    classifier.fit(X_train, labels_train)

    preds_test = classifier.predict(X_test)
    logger.info(
        "\n=== Avaliação no conjunto de TESTE (20%% — %d exemplos) ===\n%s",
        len(texts_test),
        classification_report(labels_test, preds_test, zero_division=0),
    )

    # Treina o modelo final em todos os dados antes de salvar
    X_all = features.fit_transform(texts)
    classifier.fit(X_all, labels)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(features, VECTORIZER_PATH)
    joblib.dump(classifier, CLASSIFIER_PATH)
    logger.info("Artefatos salvos em: %s", MODELS_DIR)


def treinar() -> None:
    texts, labels = _load_training_data()

    logger.info("Total de exemplos: %d", len(texts))
    intents_unicos = sorted(set(labels))
    logger.info("Intenções detectadas no dataset (%d): %s", len(intents_unicos), intents_unicos)

    logger.info("\n=== Validação Cruzada Estratificada (5-fold) ===")
    _cross_validate(texts, labels, n_splits=5)

    features = _build_feature_extractor()
    classifier = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)

    _fit_and_save(features, classifier, texts, labels)


if __name__ == "__main__":
    treinar()
