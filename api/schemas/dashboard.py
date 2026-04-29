from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union

class GeometriaSchema(BaseModel):
    id: Union[str, int]
    nome: Optional[str]
    geom: str 
    area_ha: Optional[float] = None
    atributos_json: Optional[Dict] = None

class EstadoKpis(BaseModel):
    id: int
    nome: str
    sigla: str
    total_municipios: int
    area_protegida_total_ha: float 
    focos_queimada_periodo: int
    total_alertas_desmatamento: int
    total_imoveis_rurais: int

class RankingItem(BaseModel):
    municipio: str
    uf: str
    valor: float
    unidade: str
    percentual_do_estado: float 

class DashboardCompleto(BaseModel):
    estado: EstadoKpis
    rankings: Dict[str, List[RankingItem]] 