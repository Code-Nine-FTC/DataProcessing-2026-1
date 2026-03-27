# -*- coding: utf-8 -*-
from typing import List, Optional
from pydantic import BaseModel


# --- Blocos genéricos reutilizáveis ---

class GrupoItem(BaseModel):
    label: str
    valor: float


class RespostaAgrupada(BaseModel):
    grupos: List[GrupoItem]
    total: float


class SerieTemporalItem(BaseModel):
    periodo: str
    total: int


class RespostaTemporalQueimada(BaseModel):
    series: List[SerieTemporalItem]
    total: int


# --- RF-07 #9: Data do último incêndio por estado ---

class UltimoIncendioItem(BaseModel):
    estado: str
    data_ultimo_incendio: Optional[str]


class RespostaUltimoIncendio(BaseModel):
    estados: List[UltimoIncendioItem]


# --- RF-07 #13, #14, #15, #18: Sobreposições com áreas especiais ---

class ResumoSobreposicoes(BaseModel):
    imoveis_com_sobreposicao_uc: int
    imoveis_com_sobreposicao_ti: int
    imoveis_com_sobreposicao_quilombola: int
    imoveis_com_sobreposicao_assentamento: int
    total_imoveis: int
