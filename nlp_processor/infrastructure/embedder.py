# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texto(texto: str) -> np.ndarray:
    vetor = _get_model().encode(texto, normalize_embeddings=True)
    return np.array(vetor, dtype=np.float32)


def embed_batch(textos: list[str]) -> np.ndarray:
    vetores = _get_model().encode(textos, normalize_embeddings=True, batch_size=64)
    return np.array(vetores, dtype=np.float32)
