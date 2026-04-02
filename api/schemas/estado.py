# -*- coding: utf-8 -*-
from pydantic import BaseModel


class ResponseEstado(BaseModel):
    id: int
    sigla: str | None
    nome: str | None


class ResponseMunicipioSimples(BaseModel):
    id: int
    nome: str | None
    codigo_ibge: str | None
