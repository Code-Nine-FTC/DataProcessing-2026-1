"""
Pipeline CAR - Cadastro Ambiental Rural

Fonte: Serviço Florestal Brasileiro via TerraBrasilis
URL: http://terrabrasilis.dpi.inpe.br/geoserver/wfs
Tabela: imovel_rural
Layer: prodes-car:car_properties (WFS 2.0.0)

Nota: Faz lookup de municipio_id a partir de nome e UF durante transformação.
"""
import logging
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest
from infrastructure.repositories import MunicipioRepository

logger = logging.getLogger(__name__)

CAR_SOURCE = DataSource(
    name="CAR - Cadastro Ambiental Rural",
    url="http://terrabrasilis.dpi.inpe.br/geoserver/wfs",
    format="WFS/GeoJSON",
    agency="Serviço Florestal Brasileiro",
    scope="nacional",
    frequency="anual",
    license="Domínio Público",
)

_NOME = ("nome_prop", "NOME_PROP", "property_name", "nome")
_CODIGO_CAR = ("codigo_car", "CODIGO_CAR", "car_code", "id_car", "codigo")
_AREA = ("area_hectare", "AREA_HECTARE", "area_ha", "area")
_SITUACAO = ("situacao_imovel", "SITUACAO_IMOVEL", "status", "situacao")
_MUNICIPIO = ("municipio", "MUNICIPIO", "mun_nome", "municipality")
_UF = ("uf", "UF", "estado", "state")
_ID_ORIG = ("gid", "GID", "id", "car_id", "cod_car")


class CARExtractor(WFSExtractor):
    """Extrator para Cadastro Ambiental Rural."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(CAR_SOURCE, wfs_client, "prodes-car:car_properties")


class CARTransformer(GeometricTransformer):
    """Transformador para dados de imóveis rurais."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="imovel_rural")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de imóvel rural."""
        props = feature.get("properties", feature)

        geometry = feature.get("geometry")
        geom_wkt = None
        centroid_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt
                # Calcular centroide
                if not geom.is_empty:
                    centroid = geom.centroid
                    if centroid:
                        centroid_wkt = f"POINT({centroid.x} {centroid.y})"

        # Buscar municipio_id
        municipio_nome = self.pick(props, _MUNICIPIO)
        uf = self.pick(props, _UF)
        municipio_id = None

        if municipio_nome and uf:
            try:
                municipio_id = self.municipio_repo.find_by_name_and_state(
                    municipio_nome, uf
                )
            except Exception as e:
                logger.warning(
                    f"Failed to find municipio {municipio_nome}/{uf}: {str(e)}"
                )

        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(self.pick(props, _ID_ORIG)),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome_imovel": self.pick(props, _NOME),
                "codigo_car": self.pick(props, _CODIGO_CAR),
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "municipio_id": municipio_id,
                "situacao_cadastral": self.pick(props, _SITUACAO),
                "centroid_wkt": centroid_wkt,
                "atributos_json": self.row_to_json(props),
            },
        )


class CARLoader(GeometricLoader):
    """Carregador para imóveis rurais."""

    def __init__(self, engine):
        super().__init__(engine, table_name="imovel_rural")

    def get_insert_query(self) -> str:
        """Query de inserção para imovel_rural."""
        return """
            INSERT INTO imovel_rural
                (id, id_origem, dataset_id, nome_imovel, codigo_car,
                 area_ha, municipio_id, situacao_cadastral, geom, centroid, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome_imovel, :codigo_car,
                 :area_ha, :municipio_id, :situacao_cadastral,
                 ST_GeomFromText(:geom_wkt, 4326),
                 ST_GeomFromText(:centroid_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """

    def _prepare_record_params(self, record: TransformedRecord, dataset_id: str) -> dict:
        """Prepara parâmetros com geometria e centroide."""
        params = super()._prepare_record_params(record, dataset_id)
        # Safe access para centroid_wkt
        if "centroid_wkt" in record.attributes:
            params["centroid_wkt"] = record.attributes.pop("centroid_wkt")
        else:
            params["centroid_wkt"] = None
        return params


class CARPipeline(BasePipeline):
    """Pipeline completa para CAR."""

    def __init__(
        self,
        extractor,
        transformer,
        loader,
        fonte_dado,
    ):
        super().__init__(extractor, transformer, loader, fonte_dado)

    def _get_dataset_name(self) -> str:
        return "CAR_TERRABRASILIS"

    def _get_dataset_description(self) -> str:
        return "Imóveis Rurais do Cadastro Ambiental Rural (CAR) - TerraBrasilis/SFB"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de CAR."""
    municipio_repo = MunicipioRepository(engine)

    extractor = CARExtractor(wfs_client)
    transformer = CARTransformer(municipio_repo)
    loader = CARLoader(engine)

    return CARPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=CAR_SOURCE,
    )
