import logging
from pathlib import Path
import geopandas as gpd

logger = logging.getLogger(__name__)

def standardize_geodataframe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Normaliza o Sistema de Referência de Coordenadas de um GeoDataFrame para EPSG:4326 (WGS 84).
    Se não for identificado um CRS de origem, adota preventivamente EPSG:4674 (SIRGAS 2000).
    """
    if gdf.crs is None:
        logger.warning("Nenhum CRS encontrado no GeoDataFrame. Imputando SIRGAS 2000 (EPSG:4674) como origem.")
        gdf.set_crs(epsg=4674, inplace=True)

    current_epsg = gdf.crs.to_epsg()
    if current_epsg != 4326:
        logger.info(f"O CRS de origem identificado é EPSG:{current_epsg}. Procedendo com projeção obrigatória para WGS 84 (EPSG:4326).")
        gdf.to_crs(epsg=4326, inplace=True)
    else:
        logger.info("Verificação de CRS aprovada. Os dados já estão compatíveis no formato EPSG:4326.")

    return gdf

def standardize_and_load_geodata(file_path: str) -> gpd.GeoDataFrame:
    """
    Carrega dados geoespaciais e normaliza o Sistema de Referência de Coordenadas para EPSG:4326 (WGS 84).
    Se não for identificado um CRS de origem, adota preventivamente EPSG:4674 (SIRGAS 2000).
    
    Args:
        file_path (str): Caminho absoluto ou relativo para o arquivo shapefile/geojson.
        
    Returns:
        gpd.GeoDataFrame: DataFrame georreferenciado normalizado.
        
    Raises:
        FileNotFoundError: Quando o arquivo alvo não existe.
        ValueError: Em caso de falha de decodificação espacial ou leitura.
    """
    if not Path(file_path).exists():
        logger.error(f"O arquivo não pôde ser encontrado no diretório: {file_path}")
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    try:
        gdf = gpd.read_file(file_path)
    except Exception as e:
        logger.error(f"Erro na tentativa de parsear o arquivo espacial ({file_path}): {e}")
        raise ValueError(f"Não foi possível carregar os dados geoespaciais: {e}")

    return standardize_geodataframe(gdf)