# -*- coding: utf-8 -*-
from typing import List, Optional
from pydantic import BaseModel

class CityData(BaseModel):
    nome: str
    amount: float

class RankingItem(BaseModel):
    municipio: str
    uf: str
    valor: float
    unidade: str   

class DashboardRankings(BaseModel):
    queimadas: List[RankingItem]
    desmatamento: List[RankingItem]
    assentamentos: List[RankingItem]
    terras_indigenas: List[RankingItem]
    quilombolas: List[RankingItem]
    unidades_conservacao: List[RankingItem]
    imoveis_rurais: List[RankingItem]