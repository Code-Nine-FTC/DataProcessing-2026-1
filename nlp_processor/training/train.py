from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import FeatureUnion

# --- Novas ferramentas necessárias para Multi-Label ---
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.multioutput import MultiOutputClassifier

from nlp_processor.training.train_data import TRAIN_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"
# IMPORTANTE: Precisamos salvar o binarizador para o classificador saber decodificar as labels no predict
BINARIZER_PATH = MODELS_DIR / "binarizer.joblib" 

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


# Ajustado para carregar os labels como lista de listas: list[list[str]]
def _load_training_data() -> tuple[list[str], list[list[str]]]:
    texts = [_preprocess(text) for text, _ in TRAIN_DATA]
    labels = [label for _, label in TRAIN_DATA]
    return texts, labels


def _build_feature_extractor() -> FeatureUnion:
    word_vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    return FeatureUnion([("word", word_vectorizer)])


def _cross_validate(texts: list[str], labels: list[list[str]], n_splits: int = 5) -> float:
    """Avalia F1-macro via CV sem vazar dados de teste no treino."""
    binarizer_cv = MultiLabelBinarizer()
    Y_all = binarizer_cv.fit_transform(labels)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    f1_scores: list[float] = []
    for fold, (train_idx, test_idx) in enumerate(kf.split(texts), 1):
        texts_train = [texts[i] for i in train_idx]
        texts_test  = [texts[i] for i in test_idx]
        Y_train, Y_test = Y_all[train_idx], Y_all[test_idx]
        feat = _build_feature_extractor()
        X_train = feat.fit_transform(texts_train)
        X_test  = feat.transform(texts_test)
        clf = MultiOutputClassifier(
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
        )
        clf.fit(X_train, Y_train)
        preds = clf.predict(X_test)
        f1 = f1_score(Y_test, preds, average="macro", zero_division=0)
        f1_scores.append(f1)
        logger.info("  Fold %d — F1-macro: %.3f", fold, f1)
    mean, std = float(np.mean(f1_scores)), float(np.std(f1_scores))
    logger.info("CV %d-fold — F1-macro: %.3f ± %.3f", n_splits, mean, std)
    return mean


def _fit_and_save(
    features: FeatureUnion,
    classifier: MultiOutputClassifier,
    binarizer: MultiLabelBinarizer,
    texts: list[str],
    labels: list[list[str]],
) -> None:
    # 1. Separa 20% para avaliação ANTES de treinar o modelo final
    texts_train, texts_test, labels_train, labels_test = train_test_split(
        texts, labels, test_size=0.20, random_state=42
    )

    # 2. Binarização das labels (ajuste apenas no treino)
    Y_train = binarizer.fit_transform(labels_train)
    Y_test  = binarizer.transform(labels_test)

    # 3. TF-IDF ajustado apenas no treino
    X_train = features.fit_transform(texts_train)
    X_test  = features.transform(texts_test)

    # 4. Treinamento
    classifier.fit(X_train, Y_train)

    # 5. Métricas no conjunto de TESTE (nunca visto durante o treino)
    preds_test = classifier.predict(X_test)
    logger.info(
        "\n=== Avaliação no conjunto de TESTE (20%% — %d exemplos) ===\n%s",
        len(texts_test),
        classification_report(Y_test, preds_test, target_names=binarizer.classes_, zero_division=0),
    )

    # 6. Treina o modelo FINAL em todos os dados para salvar
    X_all = features.fit_transform(texts)
    Y_all = binarizer.fit_transform(labels)
    classifier.fit(X_all, Y_all)

    # 7. Salvando os artefatos gerados
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(features, VECTORIZER_PATH)
    joblib.dump(classifier, CLASSIFIER_PATH)
    joblib.dump(binarizer, BINARIZER_PATH)
    logger.info("Artefatos salvos em: %s", MODELS_DIR)


def treinar() -> None:
    texts, labels = _load_training_data()

    logger.info("Total de exemplos: %d", len(texts))

    flat_intents = sorted({intent for sublist in labels for intent in sublist})
    logger.info("Intenções detectadas no dataset: %s", flat_intents)

    # CV para estimativa honesta de generalização
    logger.info("\n=== Validação Cruzada (5-fold) ===")
    _cross_validate(texts, labels, n_splits=5)

    features = _build_feature_extractor()
    binarizer = MultiLabelBinarizer()
    base_classifier = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
    classifier = MultiOutputClassifier(base_classifier)

    _fit_and_save(features, classifier, binarizer, texts, labels)


if __name__ == "__main__":
    treinar()