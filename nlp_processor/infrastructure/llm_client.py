# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
_TIMEOUT = httpx.Timeout(30.0, connect=2.0)


def disponivel() -> bool:
    return os.getenv("LLM_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


async def completar(
    mensagens: list[dict],
    max_tokens: int = 512,
    temperatura: float = 0.3,
) -> Optional[str]:
    if not disponivel():
        return None

    payload = {
        "model": _MODEL,
        "messages": mensagens,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperatura},
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(f"{_BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content")
    except Exception as exc:
        logger.warning("Ollama indisponível: %s", exc)
        return None
