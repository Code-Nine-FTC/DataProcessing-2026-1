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
from infrastructure.repositories import MunicipioRepository

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
_MUNICIPIO = ("MUNICIPIO", "municipio", "NOM_MUNICI", "mun_nome")
_UF_SIGLA = ("UF", "uf", "SIGLA_UF", "sigla_uf", "SIG_UF")


class INCRAExtractor(WFSExtractor):
    """Extrator para Assentamentos Rurais do INCRA."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(INCRA_SOURCE, wfs_client, "ass_legalizados")

    def extract(self) -> ExtractedData:
        """Extrai dados de Assentamentos do WFS (versão 1.1.0)."""
        from infrastructure.wfs_client import WFSRequest

        request = WFSRequest(
            url=self.data_source.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",  # INCRA usa WFS 1.1.0, não 2.0.0
        )

        try:
            from core.exceptions import ExtractionException
            gdf = self.wfs_client.fetch_all(request)
        except ExtractionException as e:
            logger.warning(f"Failed to fetch {self.wfs_layer}: {str(e)} - returning empty dataset")
            # Graceful degradation
            return ExtractedData(
                source=self.data_source,
                rows=[],
                metadata={"feature_count": 0},
            )

        if gdf.empty:
            logger.warning("No assentamentos fetched from INCRA - returning empty dataset")
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


class INCRATransformer(GeometricTransformer):
    """Transformador para dados de Assentamentos."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="assentamento_rural")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de assentamento. Filtra apenas SP."""
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
                    municipio_nome, uf
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
                "modalidade": self.pick(props, _MODALIDADE),
                "familias": self.safe_int(self.pick(props, _FAMILIAS)),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "municipio_id": municipio_id,
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
                 area_ha, municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :modalidade, :familias,
                 :area_ha, :municipio_id,
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
    municipio_repo = MunicipioRepository(engine)
    extractor = INCRAExtractor(wfs_client)
    transformer = INCRATransformer(municipio_repo)
    loader = INCRALoader(engine)

    return INCRAPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=INCRA_SOURCE,
    )
