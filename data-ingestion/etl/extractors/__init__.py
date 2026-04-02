"""
Extractores - Camada E do ETL
Responsável por buscar dados de fontes externas.
"""
import logging
import glob
from abc import ABC, abstractmethod
from typing import Optional

import geopandas as gpd
import pandas as pd

from core.models import ExtractedData, DataSource
from core.exceptions import ExtractionException

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Classe base para extractores."""

    def __init__(self, data_source: DataSource):
        self.data_source = data_source

    @abstractmethod
    def extract(self) -> ExtractedData:
        """Extrai dados da fonte. Implementar em subclasses."""
        pass

    def extract_with_logging(self) -> ExtractedData:
        """Extrai dados com logging."""
        logger.info(f"[{self.data_source.name}] Starting extraction...")
        try:
            result = self.extract()
            logger.info(
                f"[{self.data_source.name}] Extracted {len(result.rows)} records"
            )
            return result
        except Exception as e:
            logger.error(f"[{self.data_source.name}] Extraction failed: {str(e)}")
            raise


class WFSExtractor(BaseExtractor):
    """Extrator base para fontes WFS."""

    def __init__(self, data_source: DataSource, wfs_client, wfs_layer: str):
        super().__init__(data_source)
        self.wfs_client = wfs_client
        self.wfs_layer = wfs_layer

    def extract(self) -> ExtractedData:
        """Extrai dados do WFS."""
        from infrastructure.wfs_client import WFSRequest

        request = WFSRequest(
            url=self.data_source.url,
            layer=self.wfs_layer,
        )

        try:
            gdf = self.wfs_client.fetch_all(request)
        except ExtractionException as e:
            logger.warning(f"Failed to fetch {self.wfs_layer}: {str(e)} - returning empty dataset")
            # Graceful degradation: return empty dataset instead of failing
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={"feature_count": 0},
            )

        # Graceful degradation: return empty dataset if no data
        if gdf.empty:
            logger.warning(f"No data fetched for {self.wfs_layer} - returning empty dataset")
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={"feature_count": 0},
            )

        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={"feature_count": len(gdf), "crs": str(gdf.crs)},
        )


class CSVExtractor(BaseExtractor):
    """Extrator base para dados em CSV."""

    def __init__(self, data_source: DataSource, csv_pattern: str):
        """
        Args:
            data_source: Configuração da fonte
            csv_pattern: Padrão glob para encontrar arquivo (ex: "database/docs/*.csv")
        """
        super().__init__(data_source)
        self.csv_pattern = csv_pattern

    def _find_csv(self) -> Optional[str]:
        """Encontra o arquivo CSV mais recente."""
        files = sorted(glob.glob(self.csv_pattern))
        return files[-1] if files else None

    def _read_csv(self, filepath: str) -> pd.DataFrame:
        """Lê arquivo CSV."""
        logger.info(f"Reading CSV: {filepath}")
        df = pd.read_csv(filepath, encoding="latin-1")
        df.columns = df.columns.str.strip()
        return df

    def extract(self) -> ExtractedData:
        """Extrai dados do CSV."""
        csv_file = self._find_csv()
        if not csv_file:
            logger.warning(f"No CSV found matching pattern: {self.csv_pattern} - returning empty dataset")
            # Graceful degradation: return empty dataset instead of failing
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={
                    "row_count": 0,
                    "columns": [],
                    "source_file": None,
                },
            )

        df = self._read_csv(csv_file)
        logger.info(f"Loaded {len(df)} rows from {csv_file}")

        return ExtractedData(
            source=self.data_source,
            rows=df.to_dict("records"),
            metadata={
                "row_count": len(df),
                "columns": list(df.columns),
                "source_file": csv_file,
            },
        )
