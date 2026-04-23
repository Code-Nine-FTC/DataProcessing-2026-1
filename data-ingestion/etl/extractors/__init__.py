"""
Extractores - Camada E do ETL
Responsável por buscar dados de fontes externas.
"""
import logging
import glob
import os
from abc import ABC, abstractmethod
from typing import Optional

import geopandas as gpd
import pandas as pd
from core.models import ExtractedData, DataSource
from core.exceptions import ExtractionException
from core.crs_handler import standardize_geodataframe
from datetime import date


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

    def save_data(self,  data: ExtractedData,path: str = "output"):
        os.makedirs(path, exist_ok=True)
        gdf = gpd.GeoDataFrame(data.rows, crs="EPSG:4326")
        gdf.to_file(f"{path}/data-{date.today()}.geojson", driver='GeoJSON',engine='pyogrio')


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
        except ExtractionException:
            raise  # Propaga a excepção em vez de silenciar

        # Graceful degradation: return empty dataset if no data
        if gdf.empty:
            logger.warning(f"No data fetched for {self.wfs_layer} - returning empty dataset")
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={"feature_count": 0},
            )

        # Padronização de Coordenadas (RF-01)
        gdf = standardize_geodataframe(gdf)

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
        """Encontra o arquivo CSV mais recente pela data de modificação."""
        files = glob.glob(self.csv_pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

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


class ShapefileExtractor(BaseExtractor):
    """Extrator específico para Shapefiles de Terras Quilombolas."""

    def __init__(self, data_source: DataSource, shp_path: str):
        super().__init__(data_source)
        self.shp_path = shp_path

    def _find_shp(self) -> Optional[str]:
        """Localiza o arquivo .shp nos documentos do projeto."""
        # Se você passar apenas o diretório, buscamos qualquer .shp lá dentro
        if os.path.isdir(self.shp_path):
            files = glob.glob(os.path.join(self.shp_path, "*.shp"))
        else:
            files = glob.glob(self.shp_path)
            
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def extract(self) -> ExtractedData:
        """Extrai os dados geográficos e atributos do Shapefile."""
        shp_file = self._find_shp()
        
        if not shp_file:
            logger.warning(f"Nenhum arquivo Shapefile encontrado em: {self.shp_path}")
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={"row_count": 0, "source_file": None}
            )

        # Lendo o shapefile
        # engine='pyogrio' é mais rápido, mas 'fiona' é o padrão mais comum
        gdf = gpd.read_file(shp_file)

        # 1. Padronização de Coordenadas (Sincronizando com seu teste EPSG:4674 -> 4326) / RF-01
        gdf = standardize_geodataframe(gdf)

        # 2. Tratamento de NaNs (Opcional, mas ajuda a evitar erros no JSON/Dicionário)
        # Substitui valores nulos por None (que vira null no JSON)
        df_clean = gdf.where(pd.notnull(gdf), None)

        return ExtractedData(
            source=self.data_source,
            rows=df_clean.to_dict("records"),
            metadata={
                "row_count": len(gdf),
                "columns": list(gdf.columns),
                "crs": "EPSG:4326",
                "source_file": shp_file,
                "geometrias": list(gdf.geometry.type.unique())
            },
        )