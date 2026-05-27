# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config.settings import settings
from models.db_model import Usuario

_ALGORITHM = "HS256"


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verificar_senha(senha: str, hash_: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), hash_.encode("utf-8"))


def _criar_token(usuario_id: UUID, email: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "email": email, "exp": expira}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        return None


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(self, email: str, senha: str, nome: Optional[str]) -> Usuario:
        existente = await self._session.scalar(
            select(Usuario).where(Usuario.email == email)
        )
        if existente:
            raise ValueError("E-mail já cadastrado")

        usuario = Usuario(
            email=email,
            senha_hash=_hash_senha(senha),
            nome=nome,
        )
        self._session.add(usuario)
        await self._session.commit()
        await self._session.refresh(usuario)
        return usuario

    async def login(self, email: str, senha: str) -> str:
        usuario = await self._session.scalar(
            select(Usuario).where(Usuario.email == email, Usuario.ativo == True)  # noqa: E712
        )
        if not usuario or not _verificar_senha(senha, usuario.senha_hash):
            raise ValueError("Credenciais inválidas")

        return _criar_token(usuario.id, usuario.email)

    async def buscar_por_id(self, usuario_id: UUID) -> Optional[Usuario]:
        return await self._session.scalar(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.ativo == True)  # noqa: E712
        )
