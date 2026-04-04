"""
Entidades do domínio ambiental.
Representam conceitos de negócio mapeados do db_model.py
"""
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime, date
from uuid import UUID


@dataclass
class FonteDado:
    """Representa uma fonte de dados (origem de informação)."""
    id: Optional[UUID] = None
    nome: str = ""
    orgao_responsavel: Optional[str] = None
    url_origem: Optional[str] = None
    formato: Optional[str] = None
    periodicidade: Optional[str] = None
    escopo_geografico: Optional[str] = None
    licenca: Optional[str] = None
    ativo: bool = True


@dataclass
class Dataset:
    """Representa um conjunto de dados (batch de importação)."""
    id: Optional[UUID] = None
    fonte_dado_id: Optional[UUID] = None
    nome: str = ""
    descricao: Optional[str] = None
    versao: Optional[str] = None
    data_coleta: Optional[datetime] = None
    data_referencia: Optional[date] = None
    hash_arquivo: Optional[str] = None
    caminho_arquivo: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


@dataclass
class ImovelRural:
    """Imóvel rural cadastrado no CAR."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome_imovel: Optional[str] = None
    codigo_car: Optional[str] = None
    area_ha: Optional[float] = None
    municipio_id: Optional[int] = None
    situacao_cadastral: Optional[str] = None
    geom_wkt: Optional[str] = None
    centroid_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class UnidadeConservacao:
    """Unidade de Conservação (UC)."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome: Optional[str] = None
    categoria: Optional[str] = None
    esfera: Optional[str] = None
    grupo_snuc: Optional[str] = None
    area_ha: Optional[float] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class TerraIndigena:
    """Terra Indígena."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome: Optional[str] = None
    fase: Optional[str] = None
    area_ha: Optional[float] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class QueimadaEvento:
    """Evento de queimada detectado."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    data_ocorrencia: Optional[datetime] = None
    fonte_sensor: Optional[str] = None
    intensidade: Optional[float] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class DesmatamentoAlerta:
    """Alerta de desmatamento."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    data_ocorrencia: Optional[date] = None
    tipo_alerta: Optional[str] = None
    area_ha: Optional[float] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class AssentamentoRural:
    """Assentamento Rural."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome: Optional[str] = None
    area_ha: Optional[float] = None
    modalidade: Optional[str] = None
    familias: Optional[int] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class TerritorioQuilombola:
    """Território Quilombola."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome: Optional[str] = None
    area_ha: Optional[float] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None


@dataclass
class CamadaEstadualAmbiental:
    """Camada ambiental estadual."""
    id: Optional[UUID] = None
    id_origem: Optional[str] = None
    dataset_id: Optional[UUID] = None
    nome: Optional[str] = None
    subtipo: Optional[str] = None
    tema: Optional[str] = None
    municipio_id: Optional[int] = None
    geom_wkt: Optional[str] = None
    atributos_json: Optional[Dict[str, Any]] = None
