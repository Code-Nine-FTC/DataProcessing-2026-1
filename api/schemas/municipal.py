# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import List, Optional, Dict

class GeometriaSchema(BaseModel):
    id: str | int
    nome: Optional[str]
    geom: str
    area_ha: Optional[float] = None
    atributos_json: Optional[Dict] = None


class ResponseMunicipal(BaseModel):
    id: int
    nome: str
    codigo_ibge: str
    estado_sigla: str
    geom: str
    imoveis_rurais: List[GeometriaSchema] = []
    unidades_conservacao: List[GeometriaSchema] = []
    terras_indigenas: List[GeometriaSchema] = []
    assentamentos: List[GeometriaSchema] = []
    quilombolas: List[GeometriaSchema] = []
    alertas_desmatamento: List[GeometriaSchema] = []