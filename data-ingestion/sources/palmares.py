"""
Pipeline Palmares - Territórios Quilombolas

Fonte: Fundação Cultural Palmares / INCRA Acervo Fundiário
URL: https://acervofundiario.incra.gov.br/i3geo/ogc.php
Formato: Shapefile (via download manual)
Path: models/docs/quilombolas_sp.shp
Tabela: territorio_quilombola
"""
import logging
from datetime import date
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.extractors import ShapefileExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest
from infrastructure.repositories import MunicipioRepository

logger = logging.getLogger(__name__)

PALMARES_SOURCE = DataSource(
    name="Fundação Cultural Palmares - Territórios Quilombolas",
    url="https://acervofundiario.incra.gov.br/acervo/login.php",
    format="Shapefile",
    agency="Fundação Cultural Palmares / INCRA",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

_NOME = ("nm_comunid", "NOME_COMU", "nome_comunidade", "NOME", "NM_COMUNI")
_STATUS = ("fase", "st_titulad", "STATUS", "status_processo", "FASE")
_AREA = ("nr_area_ha", "area_calc_", "AREA_HA", "area_ha", "AREA_HECTA")
_ID_ORIG = ("nr_process", "cd_quilomb", "NR_PROCES", "nr_processo", "gid")
_MUNICIPIO = ("nm_municip", "MUNICIPIO", "municipio", "NOM_MUNICI")
_UF_SIGLA = ("cd_uf", "UF", "uf", "SIGLA_UF", "SIG_UF")
_PATH = "models/docs/quilombolas_sp.shp"


class PalmaresExtractor(ShapefileExtractor):
    def __init__(self):
        super().__init__(PALMARES_SOURCE, shp_path=_PATH)

    def extract(self) -> ExtractedData:
        data = super().extract()

        if data.rows:
            logger.info(f"Salvando {len(data.rows)} registros de Palmares em output/")
            self.save_data(data=data, path="output/palmares")
        else:
            logger.warning("Nenhum dado encontrado para extrair de Palmares.")

        return data


class PalmaresTransformer(GeometricTransformer):

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="territorio_quilombola")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        props = feature.get("properties", feature)

        uf = self.pick(props, _UF_SIGLA)
        if uf and str(uf).upper() != "SP":
            return None

        geometry = feature.get("geometry")
        geom_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt

        municipio_nome = self.pick(props, _MUNICIPIO)
        municipio_id = None
        if municipio_nome and uf:
            try:
                municipio_id = self.municipio_repo.find_by_name_and_state(
                    municipio_nome, uf, geom_wkt=geom_wkt
                )
            except Exception as e:
                logger.warning(f"Failed to find municipio {municipio_nome}/{uf}: {str(e)}")

        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(self.pick(props, _ID_ORIG)),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome": self.pick(props, _NOME),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "municipio_id": municipio_id,
                "atributos_json": self.row_to_json(props),
            },
        )


class PalmaresLoader(GeometricLoader):

    def __init__(self, engine):
        super().__init__(engine, table_name="territorio_quilombola")

    def get_insert_query(self) -> str:
        return """
            INSERT INTO territorio_quilombola
                (id, id_origem, dataset_id, nome, area_ha,
                 municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :area_ha,
                 :municipio_id,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class PalmaresPipeline(BasePipeline):

    def _get_dataset_name(self) -> str:
        return "QUILOMBOLA_PALMARES"

    def _get_dataset_description(self) -> str:
        return "Territórios Quilombolas do Brasil - Acervo Fundiário INCRA/FCP"


def create_pipeline(engine, wfs_client=None):
    municipio_repo = MunicipioRepository(engine)
    extractor = PalmaresExtractor()
    transformer = PalmaresTransformer(municipio_repo)
    loader = PalmaresLoader(engine)

    return PalmaresPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=PALMARES_SOURCE,
    )
