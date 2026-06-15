import asyncio
import socket
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.core.container import DockerContainer

from models.db_model import Base

_DB_IMAGE = "test-db:latest"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _wait_for_pg(cid: str, timeout: int = 60) -> None:
    for _ in range(timeout):
        try:
            r = subprocess.run(
                ["docker", "exec", cid, "pg_isready", "-h", "localhost", "-U", "test"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"PostgreSQL not ready after {timeout}s")


def _check_tcp_port(host: str, port: int, timeout: int = 60) -> None:
    for _ in range(timeout):
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except (OSError, ConnectionRefusedError):
            pass
        time.sleep(1)
    raise RuntimeError(f"TCP port {host}:{port} not reachable after {timeout}s")


@pytest.fixture(scope="session")
def postgis_container():
    container = DockerContainer(_DB_IMAGE)
    container.with_env("POSTGRES_USER", "test")
    container.with_env("POSTGRES_PASSWORD", "test")
    container.with_env("POSTGRES_DB", "test_db")
    container.with_env("POSTGRES_HOST_AUTH_METHOD", "trust")
    container.with_exposed_ports(5432)

    container.start()

    cid = container.get_wrapped_container().id
    _wait_for_pg(cid)

    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))
    _check_tcp_port(host, port)

    yield container, host, port

    container.stop()


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgis_container):
    _container, host, port = postgis_container
    url = f"postgresql+asyncpg://test:test@{host}:{port}/test_db"

    engine = create_async_engine(
        url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": "disable"},
    )

    for attempt in range(10):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.run_sync(Base.metadata.create_all)

                sql_path = Path(__file__).parents[1] / "fixtures" / "seed.sql"
                if sql_path.exists():
                    for stmt in sql_path.read_text(encoding="utf-8").split(";"):
                        s = stmt.strip()
                        if s:
                            await conn.execute(text(s))
            break
        except Exception:
            if attempt == 9:
                raise
            await asyncio.sleep(2)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        await session.close()
        try:
            await transaction.rollback()
        except Exception:
            pass
        await connection.close()


from tests.integration.helpers import test_client, count_rows  # noqa: E402, F401
