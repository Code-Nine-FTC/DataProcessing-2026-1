"""
Pipeline Palmares - Territórios Quilombolas

Fonte: Fundação Cultural Palmares / INCRA Acervo Fundiário
URL: https://acervofundiario.incra.gov.br/i3geo/ogc.php
Tabela: territorio_quilombola
Layer: quilombola_titulado (WFS 1.1.0)
"""
import logging
from datetime import date
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest

logger = logging.getLogger(__name__)

PALMARES_SOURCE = DataSource(
    name="Fundação Cultural Palmares - Territórios Quilombolas",
    url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    format="WFS/GeoJSON",
    agency="Fundação Cultural Palmares / INCRA",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

_NOME = ("NOME_COMU", "nome_comunidade", "NOME", "nome", "NM_COMUNI")
_STATUS = ("STATUS", "status_processo", "FASE", "fase", "SIT_FUNDO")
_AREA = ("AREA_HA", "area_ha", "AREA_HECTA", "area")
_ID_ORIG = ("NR_PROCES", "nr_processo", "gid", "FID", "id")


class PalmaresExtractor(WFSExtractor):
    """Extrator para Territórios Quilombolas."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(PALMARES_SOURCE, wfs_client, "quilombola_titulado")

    def extract(self) -> ExtractedData:
        """Extrai dados de Territórios Quilombolas do WFS."""
        request = WFSRequest(
            url=self.data_source.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",  # INCRA usa WFS 1.1.0
        )

        gdf = self.wfs_client.fetch_all(request)

        if gdf.empty:
            logger.warning("No quilombola territories fetched from Palmares - returning empty dataset")
            # Graceful degradation: return empty dataset instead of failing
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


class PalmaresTransformer(GeometricTransformer):
    """Transformador para dados de Territórios Quilombolas."""

    def __init__(self):
        super().__init__(table_name="territorio_quilombola")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de território quilombola."""
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
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "atributos_json": self.row_to_json(props),
            },
        )


class PalmaresLoader(GeometricLoader):
    """Carregador para Territórios Quilombolas."""

    def __init__(self, engine):
        super().__init__(engine, table_name="territorio_quilombola")

    def get_insert_query(self) -> str:
        """Query de inserção para territorio_quilombola."""
        return """
            INSERT INTO territorio_quilombola
                (id, id_origem, dataset_id, nome, area_ha,
                 geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :area_ha,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class PalmaresPipeline(BasePipeline):
    """Pipeline completa para Palmares."""

    def _get_dataset_name(self) -> str:
        return "QUILOMBOLA_PALMARES"

    def _get_dataset_description(self) -> str:
        return "Territórios Quilombolas do Brasil - Acervo Fundiário INCRA/FCP"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de Palmares."""
    extractor = PalmaresExtractor(wfs_client)
    transformer = PalmaresTransformer()
    loader = PalmaresLoader(engine)

    return PalmaresPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=PALMARES_SOURCE,
    )
