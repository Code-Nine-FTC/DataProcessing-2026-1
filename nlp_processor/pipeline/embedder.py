from __future__ import annotations

import logging
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

from nlp_processor.training.train_data import TRAIN_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
VECTORIZER_PATH = MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODELS_DIR / "intent_classifier.joblib"

MIN_F1_THRESHOLD = 0.70
CV_SPLITS = 5

_preprocessor = None


def _get_preprocessor():
    global _preprocessor
    if _preprocessor is None:
        from nlp_processor.pipeline.preprocessor import AdvancedGeoASGPreprocessor
        _preprocessor = AdvancedGeoASGPreprocessor()
    return _preprocessor


def _preprocess(text: str) -> str:
    return _get_preprocessor().process(text)["text_for_classifier"]


def _load_training_data() -> tuple[list[str], list[str]]:
    texts = [_preprocess(text) for text, _ in TRAIN_DATA]
    labels = [label for _, label in TRAIN_DATA]
    return texts, labels


def _build_feature_extractor() -> FeatureUnion:
    word_vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        min_df=1,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    char_vectorizer = TfidfVectorizer(
        ngram_range=(3, 4),
        analyzer="char_wb",
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    return FeatureUnion([("word", word_vectorizer), ("char", char_vectorizer)])


def _build_classifier() -> LogisticRegression:
    return LogisticRegression(
        max_iter=1000,
        C=0.5,
        class_weight="balanced",
        solver="lbfgs",
    )


def _evaluate(pipeline: Pipeline, texts: list[str], labels: list[str]) -> float:
    cv = StratifiedKFold(n_splits=CV_SPLITS, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, texts, labels, cv=cv, scoring="f1_macro")
    logger.info("F1-macro (CV %d-fold): %.3f ± %.3f", CV_SPLITS, scores.mean(), scores.std())

    if scores.mean() < MIN_F1_THRESHOLD:
        logger.warning(
            "F1-macro abaixo de %.2f (%.3f). Adicione mais exemplos em train_data.py.",
            MIN_F1_THRESHOLD,
            scores.mean(),
        )

    return scores.mean()


def _fit_and_save(features: FeatureUnion, classifier: LogisticRegression, texts: list[str], labels: list[str]) -> None:
    X = features.fit_transform(texts)
    classifier.fit(X, labels)

    predictions = classifier.predict(X)
    logger.info("\n%s", classification_report(labels, predictions, target_names=sorted(set(labels))))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(features, VECTORIZER_PATH)
    joblib.dump(classifier, CLASSIFIER_PATH)
    logger.info("Artefatos salvos em: %s", MODELS_DIR)


def treinar() -> None:
    texts, labels = _load_training_data()

    logger.info("Total de exemplos: %d", len(texts))
    logger.info("Intenções detectadas: %s", sorted(set(labels)))

    features = _build_feature_extractor()
    classifier = _build_classifier()

    _evaluate(Pipeline([("features", features), ("clf", classifier)]), texts, labels)
    _fit_and_save(features, classifier, texts, labels)


if __name__ == "__main__":
    treinar()