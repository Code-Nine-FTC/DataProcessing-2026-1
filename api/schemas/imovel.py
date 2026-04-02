# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional


class ResponseImovel(BaseModel):
    id: str
    nome_imovel: str | None
    codigo_car: str | None
    area_ha: float | None
    situacao_cadastral: str | None
    municipio_id: int | None
    geom: str | None


class ResponseQueimadaRelacao(BaseModel):
    id: str
    data_ocorrencia: str | None
    fonte_sensor: str | None
    intensidade: float | None
    distancia_m: float | None
    dentro_imovel: bool | None


class ResponseDesmatamentoRelacao(BaseModel):
    id: str
    tipo_alerta: str | None
    area_ha: float | None
    data_ocorrencia: str | None
    area_intersecao_ha: float | None
    percentual_sobreposicao: float | None
