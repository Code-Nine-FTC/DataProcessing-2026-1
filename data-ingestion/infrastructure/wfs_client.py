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

from core.crs_handler import standardize_geodataframe
from core.geometry_validator import validate_and_clean_geometries
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
    # Se False, faz apenas UMA requisição sem startIndex (para servidores que não suportam paginação)
    paginate: bool = True
    cql_filter: Optional[str] = None


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
                # WFS 2.0 usa "count"; WFS 1.x usa "maxFeatures"
                count_key = "count" if request.wfs_version == "2.0.0" else "maxFeatures"
                params = {
                    "service": "WFS",
                    "version": request.wfs_version,
                    "request": "GetFeature",
                    "typeName": request.layer,
                    "outputFormat": request.output_format,
                    "srsName": request.crs,
                    count_key: request.batch_size,
                }

                # startIndex só é adicionado se paginação estiver habilitada
                # (alguns servidores WFS 1.1.0 não suportam startIndex e retornam ExceptionReport)
                if request.paginate:
                    params["startIndex"] = start

                effective_bbox = (
                    request.bbox
                    if request.bbox is not None
                    else self.config.bbox
                )
                if effective_bbox:
                    params["bbox"] = effective_bbox

                if request.cql_filter:
                    params["CQL_FILTER"] = request.cql_filter

                logger.info(
                    f"Fetching {request.layer} ({start}–{start + request.batch_size})..."
                )

                # --- CONFIGURAÇÃO ADICIONADA: Simula um navegador real para evitar o erro 403 ---
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*"
                }

                response = requests.get(
                    request.url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()

                chunk = gpd.read_file(io.BytesIO(response.content))

                if chunk.empty:
                    # Verificar se o servidor retornou conteúdo real vazio
                    # ou uma resposta de erro com body vazio (evitar loop infinito)
                    if len(response.content) < 50:
                        logger.warning(
                            f"Resposta suspeita de {request.layer} (body < 50 bytes). "
                            "Encerrando paginação."
                        )
                    else:
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

        if gdf.empty:
            return gdf

        # Deduplicação se solicitada
        if deduplicate_by and deduplicate_by in gdf.columns:
            original_count = len(gdf)
            gdf = gdf.drop_duplicates(subset=[deduplicate_by])
            logger.info(
                f"Deduplicated {original_count} → {len(gdf)} "
                f"(removed {original_count - len(gdf)})"
            )

        # Garantir CRS correto com o validador robusto da API-26
        gdf = standardize_geodataframe(gdf)

        # Garantir integridade topológica e extrair MultiPoligonos para o ETL
        gdf = validate_and_clean_geometries(gdf)

        return gdf
