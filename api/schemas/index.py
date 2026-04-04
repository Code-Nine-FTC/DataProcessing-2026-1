# -*- coding: utf-8 -*-
from typing import List, Optional
from pydantic import BaseModel


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


class SerieTemporalAreaItem(BaseModel):
    periodo: str
    area_ha: float


class RespostaTemporalDesmatamento(BaseModel):
    series: List[SerieTemporalAreaItem]
    total_ha: float


class UltimoIncendioItem(BaseModel):
    estado: str
    data_ultimo_incendio: Optional[str]


class RespostaUltimoIncendio(BaseModel):
    estados: List[UltimoIncendioItem]


class ResumoSobreposicoes(BaseModel):
    imoveis_com_sobreposicao_uc: int
    imoveis_com_sobreposicao_ti: int
    imoveis_com_sobreposicao_quilombola: int
    imoveis_com_sobreposicao_assentamento: int
    total_imoveis: int


class QueimadaDentroForaItem(BaseModel):
    dentro_imovel: bool
    total: int


class RespostaQueimadaDentroFora(BaseModel):
    grupos: List[QueimadaDentroForaItem]
    total: int
