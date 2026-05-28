# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UsuarioResponse
from api.services.auth_service import AuthService
from api.utils.auth import get_current_user
from models.database import SessionConnection
from models.db_model import Usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um novo usuário",
)
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(SessionConnection.session),
) -> UsuarioResponse:
    try:
        usuario = await AuthService(session).registrar(req.email, req.senha, req.nome)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UsuarioResponse.model_validate(usuario)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autentica e retorna um JWT",
)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(SessionConnection.session),
) -> TokenResponse:
    try:
        token = await AuthService(session).login(req.email, req.senha)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UsuarioResponse,
    summary="Retorna os dados do usuário autenticado",
)
async def me(current_user: Usuario = Depends(get_current_user)) -> UsuarioResponse:
    return UsuarioResponse.model_validate(current_user)
