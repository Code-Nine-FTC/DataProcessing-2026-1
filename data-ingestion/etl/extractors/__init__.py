"""
Extractores - Camada E do ETL
Responsável por buscar dados de fontes externas.
"""
import logging
from abc import ABC, abstractmethod

import geopandas as gpd

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

        gdf = self.wfs_client.fetch_all(request)

        if gdf.empty:
            raise ExtractionException(f"No data fetched from {self.wfs_layer}")

        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={"feature_count": len(gdf), "crs": str(gdf.crs)},
        )
