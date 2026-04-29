from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union

# --- 1. Estruturas de Geometria (Baseado no seu db_model.py) ---
class GeometriaSchema(BaseModel):
    id: Union[str, int]
    nome: Optional[str]
    geom: str # Retorno ST_AsText ou GeoJSON do banco
    area_ha: Optional[float] = None
    atributos_json: Optional[Dict] = None

# --- 2. Métricas de Destaque do Estado (Para o Header) ---
class EstadoKpis(BaseModel):
    id: int
    nome: str
    sigla: str
    total_municipios: int
    area_protegida_total_ha: float # Soma de UCs, TIs e Quilombos
    focos_queimada_periodo: int
    total_alertas_desmatamento: int
    total_imoveis_rurais: int

# --- 3. Rankings (Top 15) ---
class RankingItem(BaseModel):
    municipio: str
    uf: str
    valor: float
    unidade: str
    percentual_do_estado: float 

# --- 4. Objeto Raiz do Dashboard ---
class DashboardCompleto(BaseModel):
    estado: EstadoKpis
    rankings: Dict[str, List[RankingItem]] 
    listagens_municipais: Optional[Dict[str, List[GeometriaSchema]]] = None