"""
Pipeline INCRA - Assentamentos Rurais

Fonte: Acervo Fundiário INCRA
URL: https://acervofundiario.incra.gov.br/i3geo/ogc.php
Tabela: assentamento_rural
Layer: ass_legalizados (WFS 1.1.0)
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

INCRA_SOURCE = DataSource(
    name="INCRA - Assentamentos Rurais",
    url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    format="WFS/GeoJSON",
    agency="Instituto Nacional de Colonização e Reforma Agrária",
    scope="nacional",
    frequency="irregular",
    license="Dados Abertos Gov",
)

_NOME = ("NOME_PROJE", "nome_projeto", "NOME", "nome")
_FAMILIAS = ("QTDE_FAMIL", "num_familias", "familias", "QT_FAMILIA")
_MODALIDADE = ("MODALI", "modalidade", "MODALIDADE", "mod")
_AREA = ("AREA_HECTA", "area_ha", "AREA_HA", "area")
_ID_ORIG = ("CD_SIPRA", "cod_sipra", "gid", "FID", "id")


class INCRAExtractor(WFSExtractor):
    """Extrator para Assentamentos Rurais do INCRA."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(INCRA_SOURCE, wfs_client, "ass_legalizados")

    def extract(self) -> ExtractedData:
        """Extrai dados de Assentamentos do WFS (versão 1.1.0)."""
        request = WFSRequest(
            url=self.data_source.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",  # INCRA usa WFS 1.1.0, não 2.0.0
        )

        gdf = self.wfs_client.fetch_all(request)

        if gdf.empty:
            raise Exception("No assentamentos fetched from INCRA")

        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={"feature_count": len(gdf), "crs": str(gdf.crs)},
        )


class INCRATransformer(GeometricTransformer):
    """Transformador para dados de Assentamentos."""

    def __init__(self):
        super().__init__(table_name="assentamento_rural")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de assentamento."""
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
                "modalidade": self.pick(props, _MODALIDADE),
                "familias": self.safe_int(self.pick(props, _FAMILIAS)),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "atributos_json": self.row_to_json(props),
            },
        )


class INCRALoader(GeometricLoader):
    """Carregador para Assentamentos."""

    def __init__(self, engine):
        super().__init__(engine, table_name="assentamento_rural")

    def get_insert_query(self) -> str:
        """Query de inserção para assentamento_rural."""
        return """
            INSERT INTO assentamento_rural
                (id, id_origem, dataset_id, nome, modalidade, familias,
                 area_ha, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :modalidade, :familias,
                 :area_ha,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class INCRAPipeline(BasePipeline):
    """Pipeline completa para INCRA."""

    def _get_dataset_name(self) -> str:
        return "ASSENTAMENTOS_INCRA"

    def _get_dataset_description(self) -> str:
        return "Assentamentos Rurais do Brasil - Acervo Fundiário INCRA"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de INCRA."""
    extractor = INCRAExtractor(wfs_client)
    transformer = INCRATransformer()
    loader = INCRALoader(engine)

    return INCRAPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=INCRA_SOURCE,
    )
