import os
import tempfile
import pytest
import geopandas as gpd
from shapely.geometry import Point

import sys
sys.path.insert(0, "data-ingestion")
from core.crs_handler import standardize_and_load_geodata

@pytest.fixture
def mock_shapefile_sirgas():
    """Fixture de inicialização que desenha em runtime um shapefile local utilizando EPSG:4674"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_path = os.path.join(tmpdir, "sirgas_data.shp")
        
        gdf = gpd.GeoDataFrame(
            {'id': [1, 2], 'name': ['Feature A', 'Feature B']},
            geometry=[Point(-46.6333, -23.5505), Point(-43.1729, -22.9068)],
            crs="EPSG:4674"
        )
        gdf.to_file(fake_path)
        yield fake_path

@pytest.fixture
def mock_geojson_untracked():
    """Fixture de inicialização que emula arquivos com referenciamentos omitidos (sem CRS)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_path = os.path.join(tmpdir, "orphan_data.geojson")
        
        gdf = gpd.GeoDataFrame(
            {'id': [100]},
            geometry=[Point(-50.0, -10.0)]
        )
        # Ao não exportar um atributo CRS nativo, verificamos o poder do 'Fallback'.
        gdf.to_file(fake_path, driver="GeoJSON")
        yield fake_path

def test_standardization_converts_sirgas_to_wgs(mock_shapefile_sirgas):
    """
    Testa que qualquer dado em epsg:4674 é transformado de fato no target epsg:4326.
    """
    gdf_normalized = standardize_and_load_geodata(mock_shapefile_sirgas)
    
    assert gdf_normalized is not None
    assert gdf_normalized.crs is not None
    assert gdf_normalized.crs.to_epsg() == 4326, "Diferença crs: a conversão re-projetiva falhou."
    assert len(gdf_normalized) == 2

def test_standardization_heals_untracked_files_to_wgs(mock_geojson_untracked):
    """
    Testa se arquivos omissos não explodem e adotam EPSG 4674 antes de virar WGS 84.
    """
    gdf_normalized = standardize_and_load_geodata(mock_geojson_untracked)
    
    assert gdf_normalized is not None
    assert gdf_normalized.crs is not None
    assert gdf_normalized.crs.to_epsg() == 4326, "Validação de fallback falhou ao converter um dataset virgem do zero."