import os
import logging
import geopandas as gpd
import zipfile
import json
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline

logger = logging.getLogger(__name__)

# =========================
# SOURCE
# =========================
SICAR_SOURCE = DataSource(
    name="SICAR - Assentamentos Rurais",
    url="https://github.com/urbanogilson/SICAR",
    format="SHP/GeoJSON",
    agency="SICAR",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

# =========================
# EXTRACTOR
# =========================
class SICARExtractor:

    def __init__(self, file_path, state_code='SP', **kwargs):
        import traceback

        print("KWARGS:", kwargs)

        if kwargs:
            print("\n🚨 STACK TRACE:\n")
            traceback.print_stack()
            raise Exception("Alguém está passando argumento inválido!")

        self.file_path = file_path
        self.state_code = state_code
        self.data_source = SICAR_SOURCE

    def download_if_needed(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

            from SICAR import Sicar, State, Polygon

            car = Sicar()
            state_enum = getattr(State, self.state_code)

            polygon_enum = Polygon.AREA_PROPERTY

            car.download_state(
                state_enum,
                polygon_enum,
                folder=os.path.dirname(self.file_path)
            )

    def _find_shapefile(self):
        folder = os.path.dirname(self.file_path)

        for root, _, files in os.walk(folder):
            for file in files:
                if file.endswith(".shp"):
                    return os.path.join(root, file)

        raise FileNotFoundError("Nenhum shapefile encontrado")

    def _extract_zip_files(self, folder):
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(".zip"):
                    zip_path = os.path.join(root, file)

                    print(f"📦 Extraindo: {zip_path}")

                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(root)

    def extract(self) -> ExtractedData:
        self.download_if_needed()

        # 🔥 NOVO PASSO
        self._extract_zip_files(os.path.dirname(self.file_path))

        shp_path = self._find_shapefile()

        gdf = gpd.read_file(shp_path)

        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={"feature_count": len(gdf)},
        )

# =========================
# TRANSFORMER
# =========================
class SICARTransformer(GeometricTransformer):

    def __init__(self, municipio_repo):
        super().__init__(table_name="assentamento_rural")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(feature.get("ID") or feature.get("FID")),
            table_name=self.table_name,
            geometry=feature.get("geometry"),
          attributes={"atributos_json": json.dumps(feature, default=str)}
        )

# =========================
# LOADER
# =========================
class SICARLoader(GeometricLoader):

    def __init__(self, engine):
        super().__init__(engine, table_name="assentamento_rural")

    def get_insert_query(self) -> str:
        return """
            INSERT INTO assentamento_rural
            (id, id_origem, dataset_id, atributos_json)
            VALUES
            (:id, :id_origem, :dataset_id, CAST(:atributos_json AS JSONB))
        """
# =========================
# PIPELINE
# =========================
class SICARPipeline(BasePipeline):

    def _get_dataset_name(self) -> str:
        return "ASSENTAMENTOS_SICAR"