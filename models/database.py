# -*- coding: utf-8 -*-

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from api.config.settings import settings
from api.utils.common import Singleton


class Database(metaclass=Singleton):
    def __init__(self) -> None:
        self._engine: AsyncEngine = self._create_engine()
        self._session_maker: async_sessionmaker[AsyncSession] = self._create_session_factory()

    async def ping(self) -> None:
        async with self.session as session:
            await session.execute(text("SELECT 1;"))

    @property
    def session(self) -> AsyncSession:
        return self._session_maker()

    @staticmethod
    def _create_engine() -> AsyncEngine:
        return create_async_engine(
            settings.DATABASE_URL,
        )

    def _create_session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def close(self) -> None:
        await self._engine.dispose()


class SessionConnection:
    @staticmethod
    async def session() -> AsyncGenerator[AsyncSession, None]:
        async with Database().session as session:
            yield session