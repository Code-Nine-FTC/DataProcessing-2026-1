# -*- coding: utf-8 -*-
from enum import Enum
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


class TipoAreaSobreposicao(str, Enum):
    todos = "todos"
    uc = "uc"
    ti = "ti"
    quilombo = "quilombo"
    assentamento = "assentamento"


class SobreposicaoAreaItem(BaseModel):
    tipo_area: str
    imovel_id: str
    codigo_car: Optional[str]
    nome_imovel: Optional[str]
    municipio: Optional[str]
    estado: Optional[str]
    area_id: str
    area_nome: Optional[str]
    area_imovel_ha: Optional[float]
    area_intersecao_ha: Optional[float]
    percentual_sobreposicao: Optional[float]
    tipo_relacao: Optional[str]


class RespostaSobreposicoesAreas(BaseModel):
    tipo_area: str
    itens: List[SobreposicaoAreaItem]
    total: int


class QueimadaDentroForaItem(BaseModel):
    dentro_imovel: bool
    total: int


class RespostaQueimadaDentroFora(BaseModel):
    grupos: List[QueimadaDentroForaItem]
    total: int


class ProximidadeItem(BaseModel):
    imovel_id: str
    nome_imovel: Optional[str]
    municipio: Optional[str]
    alerta_id: str
    tipo_alerta: Optional[str]
    distancia_m: float


class RespostaProximidade(BaseModel):
    itens: List[ProximidadeItem]
    total: int


class BufferResultItem(BaseModel):
    alerta_id: str
    tipo_alerta: Optional[str]
    municipio: Optional[str]
    imovel_id: str
    nome_imovel: Optional[str]
    area_buffer_ha: float
    buffer_geojson: Optional[str]


class RespostaBuffer(BaseModel):
    raio_km: float
    itens: List[BufferResultItem]
    total: int


class ProximidadeQueimadaItem(BaseModel):
    imovel_id: str
    nome_imovel: Optional[str]
    municipio: Optional[str]
    queimada_id: str
    bioma: Optional[str]
    distancia_m: float
    nivel_risco_ambiental: Optional[str] = None


class RespostaProximidadeQueimada(BaseModel):
    itens: List[ProximidadeQueimadaItem]
    total: int
