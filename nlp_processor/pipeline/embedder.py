# -*- coding: utf-8 -*-
"""
Embedder local usando sentence-transformers para RAG.
Modelo: paraphrase-multilingual-mpnet-base-v2 (768 dims, suporte ao português).

NOTA: O campo DocumentoTrecho.embedding deve ser Vector(768).
      Atualize o db_model e gere uma migration se necessário.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIM = 768


class LocalEmbedder:
    """Wrapper para o modelo de embedding local (sentence-transformers)."""

    def __init__(self, model_name: str = _EMBED_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info("Embedder carregado: %s", self._model_name)
        except ImportError as exc:
            raise ImportError(
                "Instale sentence-transformers: pip install sentence-transformers"
            ) from exc

    def embed(self, texto: str) -> list[float]:
        """Retorna embedding como lista de floats."""
        self._ensure_loaded()
        vector = self._model.encode(texto, convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, textos: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        vectors = self._model.encode(textos, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


_embedder_instance: Optional[LocalEmbedder] = None


def get_embedder() -> LocalEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LocalEmbedder()
    return _embedder_instance
