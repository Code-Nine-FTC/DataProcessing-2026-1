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
from infrastructure.repositories import MunicipioRepository

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

_NOME = ("terrai_nome", "terranome", "TERRANOME", "nome_ti", "nome")
_FASE = ("fase_ti", "FASE_TI", "fase", "situacao")
_AREA = ("superficie_perimetro_ha", "areaoficia", "AREAOFICIA", "area_ha", "area")
_ID_ORIG = ("gid", "terrai_codigo", "FID", "cod_ti", "id")
_MUNICIPIO = ("municipio_nome", "municipio", "MUNICIPIO", "mun_nome")
_UF_SIGLA = ("uf_sigla", "UF", "uf", "sigla_uf")


class FUNAIExtractor(WFSExtractor):
    """Extrator para Terras Indígenas da FUNAI."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(FUNAI_SOURCE, wfs_client, "Funai:tis_poligonais")

    def extract(self) -> ExtractedData:
        """Extrai dados do WFS usando WFS 1.1.0 sem paginação (servidor não suporta startIndex)."""
        request = WFSRequest(
            url=self.data_source.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",
            batch_size=10_000,   # maior que o total esperado (~655)
            paginate=False,      # FUNAI GeoServer rejeita startIndex com WFS 1.1.0
        )

        gdf = self.wfs_client.fetch_all(request)

        if gdf.empty:
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


class FUNAITransformer(GeometricTransformer):
    """Transformador para dados de Terras Indígenas."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="terra_indigena")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de terra indígena. Filtra apenas SP."""
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
                "fase": self.pick(props, _FASE),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "municipio_id": municipio_id,
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
                 municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :fase, :area_ha,
                 :municipio_id,
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
    municipio_repo = MunicipioRepository(engine)
    extractor = FUNAIExtractor(wfs_client)
    transformer = FUNAITransformer(municipio_repo)
    loader = FUNAILoader(engine)

    return FUNAIPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=FUNAI_SOURCE,
    )
