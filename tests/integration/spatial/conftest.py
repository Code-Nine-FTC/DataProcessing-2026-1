import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from geoalchemy2 import WKTElement

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test_db"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def event_loop_session():
    """Event loop compartilhado por sessão para performance."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
async def engine():
    engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(engine):
    """Session com transação aninhada para isolamento de testes."""
    async with AsyncSession(engine) as session:
        async with session.begin():
            yield session


@pytest.fixture
def sample_point():
    return WKTElement("POINT(-46.633 -23.583)", srid=4326)


@pytest.fixture
def sample_polygon():
    return WKTElement("POLYGON((-46.633 -23.583, -46.630 -23.585, -46.635 -23.590, -46.633 -23.583))", srid=4326)


@pytest.fixture
def sample_point_sao_paulo():
    """Ponto em São Paulo (WGS84)."""
    return WKTElement("POINT(-46.633 -23.583)", srid=4326)


@pytest.fixture
def sample_polygon_sao_paulo():
    """Polígono em São Paulo (WGS84)."""
    return WKTElement("POLYGON((-46.65 -23.60, -46.60 -23.60, -46.60 -23.55, -46.65 -23.55, -46.65 -23.60))", srid=4326)
