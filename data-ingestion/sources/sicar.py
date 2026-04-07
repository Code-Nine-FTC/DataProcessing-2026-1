"""
Pipeline SICAR - Assentamentos Rurais

Fonte: SICAR (https://github.com/urbanogilson/SICAR)
Tabela: assentamento_rural
"""
import logging
from uuid import uuid4
from core.models import ExtractedData, TransformedRecord, DataSource
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.repositories import MunicipioRepository
import geopandas as gpd

logger = logging.getLogger(__name__)

SICAR_SOURCE = DataSource(
    name="SICAR - Assentamentos Rurais",
    url="https://github.com/urbanogilson/SICAR",
    format="SHP/GeoJSON",
    agency="SICAR",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

class SICARExtractor:
    """Extrator para Assentamentos Rurais do SICAR."""
    def __init__(self, file_path, download_url=None):
        self.file_path = file_path
        self.download_url = download_url or "https://github.com/urbanogilson/SICAR/raw/master/assentamentos/assentamentos.zip"
        self.data_source = SICAR_SOURCE

    def download_if_needed(self):
        import os
        import requests
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            logger.info(f"Baixando arquivo SICAR de {self.download_url}...")
            r = requests.get(self.download_url, stream=True)
            if r.status_code == 200:
                zip_path = self.file_path if self.file_path.endswith('.zip') else self.file_path + '.zip'
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                # Extrai se for zip
                if zip_path.endswith('.zip'):
                    import zipfile
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(os.path.dirname(self.file_path))
                    logger.info(f"Arquivo SICAR extraído em {os.path.dirname(self.file_path)}")
            else:
                raise Exception(f"Falha ao baixar arquivo SICAR: {r.status_code}")

    def extract(self) -> ExtractedData:
        self.download_if_needed()
        gdf = gpd.read_file(self.file_path)
        if gdf.empty:
            logger.warning("No assentamentos fetched from SICAR - returning empty dataset")
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

class SICARTransformer(GeometricTransformer):
    """Transformador para dados de Assentamentos do SICAR."""
    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="assentamento_rural")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        props = feature.get("properties", feature)
        geometry = feature.get("geometry")
        geom_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt
        municipio_nome = props.get("MUNICIPIO") or props.get("municipio")
        uf = props.get("UF") or props.get("uf")
        municipio_id = None
        if municipio_nome and uf:
            try:
                municipio_id = self.municipio_repo.find_by_name_and_state(municipio_nome, uf)
            except Exception as e:
                logger.warning(f"Failed to find municipio {municipio_nome}/{uf}: {str(e)}")
        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(props.get("ID") or props.get("id") or props.get("FID")),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome": props.get("NOME") or props.get("nome"),
                "modalidade": props.get("MODALIDADE") or props.get("modalidade"),
                "familias": self.safe_int(props.get("FAMILIAS") or props.get("familias")),
                "area_ha": self.safe_float(props.get("AREA_HA") or props.get("area_ha")),
                "municipio_id": municipio_id,
                "atributos_json": self.row_to_json(props),
            },
        )

class SICARLoader(GeometricLoader):
    """Carregador para Assentamentos do SICAR."""
    def __init__(self, engine):
        super().__init__(engine, table_name="assentamento_rural")
    def get_insert_query(self) -> str:
        return """
            INSERT INTO assentamento_rural
                (id, id_origem, dataset_id, nome, modalidade, familias,
                 area_ha, municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :modalidade, :familias,
                 :area_ha, :municipio_id,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """

class SICARPipeline(BasePipeline):
    """Pipeline completa para SICAR."""
    def _get_dataset_name(self) -> str:
        return "ASSENTAMENTOS_SICAR"
