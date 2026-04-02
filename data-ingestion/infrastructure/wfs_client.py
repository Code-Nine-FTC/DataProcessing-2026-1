"""
Cliente WFS - Abstração para acesso a serviços WFS/GeoJSON.
"""
import io
import logging
from typing import Optional
from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
import requests

from core.exceptions import ExtractionException
from core.config import WFSConfig

logger = logging.getLogger(__name__)


@dataclass
class WFSRequest:
    """Configuração de requisição WFS."""
    url: str
    layer: str
    batch_size: int = 500
    wfs_version: str = "2.0.0"
    output_format: str = "application/json"
    crs: str = "EPSG:4326"
    # Se não for None, substitui WFSConfig.bbox; se ambos forem omitidos, não há filtro bbox.
    bbox: Optional[str] = None


class WFSClient:
    """Client reutilizável para acessar fontes WFS."""

    def __init__(self, config: WFSConfig):
        self.config = config

    def fetch(self, request: WFSRequest, start_index: int = 0) -> gpd.GeoDataFrame:
        """
        Busca features de um WFS com paginação automática.

        Args:
            request: Configuração da requisição WFS
            start_index: Índice inicial para paginação

        Returns:
            GeoDataFrame com as features

        Raises:
            ExtractionException: Se falhar ao buscar dados
        """
        gdfs = []
        start = start_index

        while True:
            try:
                params = {
                    "service": "WFS",
                    "version": request.wfs_version,
                    "request": "GetFeature",
                    "typeName": request.layer,
                    "outputFormat": request.output_format,
                    "srsName": request.crs,
                    "count": request.batch_size,
                }

                effective_bbox = (
                    request.bbox
                    if request.bbox is not None
                    else self.config.bbox
                )
                if effective_bbox:
                    params["bbox"] = effective_bbox

                # WFS 2.0 usa startIndex; versões antigas usam startPosition
                if request.wfs_version == "2.0.0":
                    params["startIndex"] = start
                else:
                    params["startPosition"] = start

                logger.info(
                    f"Fetching {request.layer} ({start}–{start + request.batch_size})..."
                )

                response = requests.get(
                    request.url,
                    params=params,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()

                chunk = gpd.read_file(io.BytesIO(response.content))

                if chunk.empty:
                    logger.info(f"No more features from {request.layer}")
                    break

                gdfs.append(chunk)
                start += len(chunk)
                logger.info(f"Got {len(chunk)} features, total so far: {start}")

                # Stop if returned fewer features than requested
                if len(chunk) < request.batch_size:
                    break

            except requests.exceptions.RequestException as e:
                raise ExtractionException(
                    f"Failed to fetch {request.layer} from {request.url}: {str(e)}"
                )
            except Exception as e:
                raise ExtractionException(
                    f"Error processing WFS response from {request.layer}: {str(e)}"
                )

        if not gdfs:
            logger.warning(f"No data fetched for {request.layer}")
            return gpd.GeoDataFrame()

        result = pd.concat(gdfs, ignore_index=True)
        logger.info(f"Total features for {request.layer}: {len(result)}")
        return result

    def fetch_all(
        self,
        request: WFSRequest,
        deduplicate_by: Optional[str] = None,
    ) -> gpd.GeoDataFrame:
        """
        Busca TODAS as features com paginação automática.

        Args:
            request: Configuração da requisição WFS
            deduplicate_by: Coluna para deduplicação (opcional)

        Returns:
            GeoDataFrame com todas as features
        """
        gdf = self.fetch(request)

        # Deduplicação se solicitada
        if deduplicate_by and deduplicate_by in gdf.columns:
            original_count = len(gdf)
            gdf = gdf.drop_duplicates(subset=[deduplicate_by])
            logger.info(
                f"Deduplicated {original_count} → {len(gdf)} "
                f"(removed {original_count - len(gdf)})"
            )

        # Garantir CRS correto
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)

        return gdf
