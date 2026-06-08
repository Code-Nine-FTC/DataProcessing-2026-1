from __future__ import annotations

import logging
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import KFold
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


def _fit_and_save(
    features: FeatureUnion, 
    classifier: MultiOutputClassifier, 
    binarizer: MultiLabelBinarizer, 
    texts: list[str], 
    labels: list[list[str]]
) -> None:
    # 1. Extração de características do texto (TF-IDF)
    X = features.fit_transform(texts)
    
    # 2. Binarização das labels (converte as listas de strings em colunas de 0 e 1)
    Y = binarizer.fit_transform(labels)
    
    # 3. Treinamento com suporte a saídas múltiplas simultâneas
    classifier.fit(X, Y)

    # 4. Avaliação e exibição das métricas
    predictions = classifier.predict(X)
    logger.info("\n%s", classification_report(Y, predictions, target_names=binarizer.classes_))

    # 5. Salvando os artefatos gerados
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(features, VECTORIZER_PATH)
    joblib.dump(classifier, CLASSIFIER_PATH)
    joblib.dump(binarizer, BINARIZER_PATH)
    logger.info("Artefatos salvos em: %s", MODELS_DIR)


def treinar() -> None:
    texts, labels = _load_training_data()

    logger.info("Total de exemplos: %d", len(texts))
    
    # Extrai todas as intenções únicas de dentro das listas de forma segura
    flat_intents = sorted(list({intent for sublist in labels for intent in sublist}))
    logger.info("Intenções detectadas no dataset: %s", flat_intents)

    features = _build_feature_extractor()
    binarizer = MultiLabelBinarizer()
    
    # Cria uma regressão logística base balanceada e encapsula no MultiOutput
    base_classifier = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
    classifier = MultiOutputClassifier(base_classifier)

    _fit_and_save(features, classifier, binarizer, texts, labels)


if __name__ == "__main__":
    treinar()