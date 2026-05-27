# -*- coding: utf-8 -*-
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    senha: str
    nome: Optional[str] = None

    @field_validator("senha")
    @classmethod
    def senha_valida(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("A senha deve ter pelo menos 6 caracteres")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no máximo 72 caracteres")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioResponse(BaseModel):
    id: UUID
    email: str
    nome: Optional[str]

    model_config = {"from_attributes": True}
