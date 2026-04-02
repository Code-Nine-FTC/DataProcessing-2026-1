"""
Pipeline FUNAI - Terras Indígenas

Fonte: FUNAI GeoServer
URL: https://geoserver.funai.gov.br/geoserver/Funai/ows
Tabela: terra_indigena
Layer: Funai:tis_poligonais
"""
import logging
from datetime import date
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from core.config import WFSConfig
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest

logger = logging.getLogger(__name__)

FUNAI_SOURCE = DataSource(
    name="FUNAI - Terras Indígenas",
    url="https://geoserver.funai.gov.br/geoserver/Funai/ows",
    format="WFS/GeoJSON",
    agency="Fundação Nacional dos Povos Indígenas",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

_NOME = ("terranome", "TERRANOME", "nome_ti", "nome")
_FASE = ("fase_ti", "FASE_TI", "fase", "situacao")
_AREA = ("areaoficia", "AREAOFICIA", "area_ha", "area")
_ID_ORIG = ("gid", "FID", "cod_ti", "id")


class FUNAIExtractor(WFSExtractor):
    """Extrator para Terras Indígenas da FUNAI."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(FUNAI_SOURCE, wfs_client, "Funai:tis_poligonais")


class FUNAITransformer(GeometricTransformer):
    """Transformador para dados de Terras Indígenas."""

    def __init__(self):
        super().__init__(table_name="terra_indigena")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de terra indígena."""
        props = feature.get("properties", feature)

        geometry = feature.get("geometry")
        geom_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt

        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(self.pick(props, _ID_ORIG)),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome": self.pick(props, _NOME),
                "fase": self.pick(props, _FASE),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "atributos_json": self.row_to_json(props),
            },
        )


class FUNAILoader(GeometricLoader):
    """Carregador para Terras Indígenas."""

    def __init__(self, engine):
        super().__init__(engine, table_name="terra_indigena")

    def get_insert_query(self) -> str:
        """Query de inserção para terra_indigena."""
        return """
            INSERT INTO terra_indigena
                (id, id_origem, dataset_id, nome, fase, area_ha,
                 geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :fase, :area_ha,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class FUNAIPipeline(BasePipeline):
    """Pipeline completa para FUNAI."""

    def _get_dataset_name(self) -> str:
        return "TI_FUNAI"

    def _get_dataset_description(self) -> str:
        return "Terras Indígenas do Brasil - GeoServer FUNAI"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de FUNAI."""
    extractor = FUNAIExtractor(wfs_client)
    transformer = FUNAITransformer()
    loader = FUNAILoader(engine)

    return FUNAIPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=FUNAI_SOURCE,
    )
