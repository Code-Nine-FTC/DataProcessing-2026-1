# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union, Dict, Any

logger = logging.getLogger(__name__)

_EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIM = 768


class LocalEmbedder:
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

    def embed(self, texto: Union[str, Dict[str, Any]]) -> list[float]:
        self._ensure_loaded()
        
        if isinstance(texto, dict):
            texto_final = texto.get("text_for_entities_and_rag", "")
            if not texto_final:
                texto_final = texto.get("normalized_text", "")
        else:
            texto_final = texto

        if not str(texto_final).strip():
            return [0.0] * EMBEDDING_DIM

        vector = self._model.encode(str(texto_final), convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, textos: list[str]) -> list[list[float]]:
        """Gera embeddings em lote para os documentos do banco."""
        self._ensure_loaded()
        if not textos:
            return []
        vectors = self._model.encode(textos, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


_embedder_instance: Optional[LocalEmbedder] = None


def get_embedder() -> LocalEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LocalEmbedder()
    return _embedder_instance