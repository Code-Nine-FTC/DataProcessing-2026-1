"""
Tipos, modelos e DTOs da aplicação.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import date, datetime


@dataclass
class DataSource:
    """Configuração de uma fonte de dados."""
    name: str
    url: Optional[str] = None
    format: str = "WFS/GeoJSON"
    agency: Optional[str] = None
    scope: str = "nacional"
    frequency: str = "anual"
    license: str = "Dados Abertos Gov"


@dataclass
class ExtractedData:
    """Dados brutos extraídos da fonte."""
    source: DataSource
    rows: list
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class TransformedRecord:
    """Registro transformado pronto para carregar."""
    id: str
    id_origem: str
    table_name: str
    dataset_id: Optional[str] = None
    geometry: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadResult:
    """Resultado do carregamento."""
    total_records: int
    inserted_records: int
    failed_records: int
    errors: list = field(default_factory=list)
    loaded_at: datetime = field(default_factory=datetime.now)


class IExtractor(ABC):
    """Interface para extractores de dados."""

    @abstractmethod
    def extract(self) -> ExtractedData:
        """Extrai dados da fonte."""
        pass


class ITransformer(ABC):
    """Interface para transformadores."""

    @abstractmethod
    def transform(self, data: ExtractedData) -> list[TransformedRecord]:
        """Transforma dados brutos em registros normalizados."""
        pass


class ILoader(ABC):
    """Interface para carregadores."""

    @abstractmethod
    def load(self, records: list[TransformedRecord]) -> LoadResult:
        """Carrega registros no banco de dados."""
        pass


class IPipeline(ABC):
    """Interface para pipelines ETL."""

    @abstractmethod
    def run(self) -> LoadResult:
        """Executa a pipeline completa (Extract → Transform → Load)."""
        pass
