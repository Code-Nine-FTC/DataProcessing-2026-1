from collections.abc import AsyncGenerator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from api.router.chat import get_session as chat_get_session
from api.utils.auth import get_current_user, require_admin
from models.database import SessionConnection


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_session():
        yield db_session

    def _override_current_user():
        user = MagicMock()
        user.id = uuid4()
        user.email = "teste@teste.com"
        user.nome = "Teste"
        user.role = "admin"
        return user

    app.dependency_overrides[SessionConnection.session] = _override_session
    app.dependency_overrides[chat_get_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[require_admin] = _override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


async def count_rows(session: AsyncSession, table_name: str) -> int:
    from sqlalchemy import text
    result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    return result.scalar_one()
