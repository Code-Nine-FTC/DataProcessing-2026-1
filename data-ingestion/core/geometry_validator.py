# -*- coding: utf-8 -*-
import logging
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

logger = logging.getLogger(__name__)

def _extract_polygons(geom):
    """
    Extrai apenas Polígonos de coleções mistas geradas pelo make_valid(), 
    evitando erros de persistência em colunas MULTIPOLYGON do banco de dados.
    """
    if geom is None or geom.is_empty:
        return None
    
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
        
    if isinstance(geom, GeometryCollection):
        # Filtra apenas geometrias de área (descarta falhas de linhas ou pontos criadas em auto-interseções)
        # Flatten: MultiPolygon precisa de Polygons individuais, não de MultiPolygons aninhados
        polys = []
        for g in geom.geoms:
            if isinstance(g, Polygon):
                polys.append(g)
            elif isinstance(g, MultiPolygon):
                polys.extend(g.geoms)
        if polys:
            return MultiPolygon(polys)
            
    # Se sobrou apenas linha ou ponto solto, descarte (não é uma área utilizável)
    return None

def validate_and_clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    [RF-02] Realiza a auditoria e limpeza topológica das geometrias em memória (GeoPandas).
    1. Verifica e limpa registros inconsistentes (dados sem geometria).
    2. Aplica autocorreção (make_valid) de vértices e auto-interseções inválidas.
    3. Garante extração de polígonos consistentes para a persistência no banco.
    """
    if gdf.empty:
        return gdf

    initial_count = len(gdf)
    
    # 1. Conferir registros inconsistentes: remover linhas sem qualquer valor geográfico
    gdf = gdf.dropna(subset=['geometry']).copy()
    
    # 2. Verificar geometrias inválidas: aplica autocorreção do GEOS do C++
    invalid_mask = ~gdf.is_valid
    if invalid_mask.any():
        num_invalid = invalid_mask.sum()
        logger.warning(f"Encontradas {num_invalid} geometrias corrompidas. Acionando autocorreção (make_valid)...")
        gdf['geometry'] = gdf['geometry'].make_valid()
    
    # 3. Garantir dados utilizáveis e coesos para colunas MultiPolygon da API
    # Reduz coleções geradas pela correção cruzada que continham 'restos' de lixo geométrico 
    gdf['geometry'] = gdf['geometry'].apply(_extract_polygons)
    
    # Filtra sobras inválidas, nulas ou vazias após a extração
    gdf = gdf.dropna(subset=['geometry'])
    gdf = gdf[~gdf.is_empty]
    gdf = gdf[gdf.is_valid]
    
    final_count = len(gdf)
    if initial_count != final_count:
        logger.warning(f"Toxidade isolada: {initial_count - final_count} registros vazios ou irrecuperáveis foram purgados do lote.")
    
    return gdf
