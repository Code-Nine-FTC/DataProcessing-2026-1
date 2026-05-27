# -*- coding: utf-8 -*-
import asyncio
import time
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")

_store: dict[str, tuple[Any, float]] = {}
_locks: dict[str, asyncio.Lock] = {}

DEFAULT_TTL = 300  # segundos


async def cached(key: str, ttl: int, fn: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Executa fn e armazena o resultado por ttl segundos.

    Usa um lock por chave para evitar cache stampede: se múltiplas requisições
    chegarem simultaneamente com o cache expirado, apenas uma executa fn.
    """
    entry = _store.get(key)
    if entry is not None:
        value, expires_at = entry
        if time.monotonic() < expires_at:
            return value

    if key not in _locks:
        _locks[key] = asyncio.Lock()

    async with _locks[key]:
        # Re-verifica após adquirir o lock (outro worker pode ter populado)
        entry = _store.get(key)
        if entry is not None:
            value, expires_at = entry
            if time.monotonic() < expires_at:
                return value

        value = await fn()
        _store[key] = (value, time.monotonic() + ttl)
        return value


def invalidate(key: str) -> None:
    _store.pop(key, None)


def invalidate_all() -> None:
    _store.clear()
