import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from geoalchemy2 import WKTElement

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
async def engine():
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost:5432/test_db")
    yield engine
    await engine.dispose()

@pytest.fixture()
async def db_session(engine):
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def sample_point():
    return WKTElement("POINT(-46.633 -23.583)", srid=4326)

@pytest.fixture
def sample_polygon():
    return WKTElement("POLYGON((-46.633 -23.583, -46.630 -23.585, -46.635 -23.590, -46.633 -23.583))", srid=4326)
