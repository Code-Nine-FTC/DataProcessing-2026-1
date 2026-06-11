# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from api.config.settings import settings
from models.database import Database
from models.seed_usuarios import seed_usuarios
from nlp_processor import orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
    try:
        await Database().ping()
        if settings.APP_ENV.lower() == "development":
            seed_usuarios()
        async with Database().session as session:
            await orchestrator.warm_up(session)
        yield
    finally:
        await Database().close()