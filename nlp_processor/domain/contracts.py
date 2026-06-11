# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from nlp_processor.domain.enums import Dominio, Operacao


class LocalConsulta(BaseModel):
    municipio_nome: Optional[str] = None
    municipio_id: Optional[int] = None
    regiao_administrativa_nome: Optional[str] = None
    regiao_administrativa_id: Optional[int] = None
    codigo_car: Optional[str] = None


class PeriodoConsulta(BaseModel):
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None


class FiltrosConsulta(BaseModel):
    bioma: Optional[str] = None
    categoria_uc: Optional[str] = None
    esfera_uc: Optional[str] = None
    grupo_snuc: Optional[str] = None
    fase_ti: Optional[str] = None
    tipo_alerta: Optional[str] = None
    sensor: Optional[str] = None
    limite: int = 50
    tema_ranking: Optional[str] = None
    tema_sobreposicao_a: Optional[str] = None
    tema_sobreposicao_b: Optional[str] = None


class ContextoEspacial(BaseModel):
    dentro_de: Optional[Dominio] = None


class TextoProcessado(BaseModel):
    original: str
    normalizado: str
    corrigido: str
    tokens: list[str]
    embedding: Optional[list[float]] = None


class QuerySpec(BaseModel):
    dominio: Dominio
    operacao: Operacao = Operacao.LISTAR
    onde: LocalConsulta = Field(default_factory=LocalConsulta)
    periodo: Optional[PeriodoConsulta] = None
    filtros: FiltrosConsulta = Field(default_factory=FiltrosConsulta)
    contexto_espacial: Optional[ContextoEspacial] = None


class PlanoConsulta(BaseModel):
    specs: list[QuerySpec]
    confianca: float
    fora_escopo: bool = False


class Fonte(BaseModel):
    nome: str
    orgao: Optional[str] = None
    url: Optional[str] = None


class ToolResult(BaseModel):
    dominio: Dominio
    operacao: Operacao
    total: int
    features: list[dict] = Field(default_factory=list)
    resumo: dict = Field(default_factory=dict)
    fontes: list[Fonte] = Field(default_factory=list)
    spec: QuerySpec
    bbox: Optional[list[float]] = None
    sql_executado: Optional[str] = None


class RespostaNLP(BaseModel):
    texto: str
    features: list[dict]
    bbox: Optional[list[float]]
    fontes: list[Fonte]
    status: str
    confianca: float
    sql_executado: Optional[str] = None
    tempo_ms: int = 0
