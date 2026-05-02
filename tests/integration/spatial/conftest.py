
import pytest
import os
import sys
import importlib
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

# Alias para permitir import data_ingestion mesmo com pasta data-ingestion
try:
    sys.modules['data_ingestion'] = importlib.import_module('data-ingestion')
except ModuleNotFoundError:
    pass

from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c

# Carrega variáveis de ambiente
load_dotenv('.env.test')
load_dotenv()

# Configuração do banco de teste
POSTGRES_USER = os.getenv("POSTGRES_USER", "test")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "test")
POSTGRES_DB = os.getenv("POSTGRES_DB", "test_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

TEST_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Cria engine uma única vez
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)





@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture para banco de teste"""
    async with TestingSessionLocal() as session:
        try:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await session.commit()
            yield session
        finally:
            await session.close()
            await engine.dispose()


@pytest.fixture
async def session(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Fixture de sessão para cada teste"""
    try:
        yield db_session
    finally:
        await db_session.rollback()
