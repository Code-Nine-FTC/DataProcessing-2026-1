"""
Pipeline DataGeo SP - Camadas Ambientais Estaduais

Fonte: DataGeo SP - Secretaria de Meio Ambiente SP
URL: https://datageo.ambiente.sp.gov.br/geoserver/datageo/ows
Tabela: camada_estadual_ambiental
Layers: Areas_Protegidas_* (configurável via DATAGEO_SP_LAYERS env)
"""
import logging
import os
from datetime import date
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.extractors import BaseExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest

logger = logging.getLogger(__name__)

DATAGEO_SOURCE = DataSource(
    name="DataGeo SP - Camadas Ambientais",
    url="https://datageo.ambiente.sp.gov.br/geoserver/datageo/ows",
    format="WFS/GeoJSON",
    agency="Secretaria de Meio Ambiente, Infraestrutura e Logística de SP",
    scope="estadual",
    frequency="irregular",
    license="Dados Abertos (DataGeo)",
)

# Camadas disponíveis
AVAILABLE_LAYERS = [
    {
        "layer": "datageo:Areas_Protegidas_PI_DG_UCs_Protecao_Integral",
        "tema": "Unidades de Conservação Estaduais",
        "subtipo": "Proteção Integral",
        "id_fields": ("OBJECTID", "id", "gid"),
        "nome_fields": ("Unidade", "nome", "NOME"),
    },
    {
        "layer": "datageo:Areas_Protegidas_US_DG_UCs_Uso_Sustentavel",
        "tema": "Unidades de Conservação Estaduais",
        "subtipo": "Uso Sustentável",
        "id_fields": ("OBJECTID", "id", "gid"),
        "nome_fields": ("Unidade", "nome", "NOME"),
    },
]


class DataGeoSPExtractor(BaseExtractor):
    """Extrator para camadas ambientais de SP."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(DATAGEO_SOURCE)
        self.wfs_client = wfs_client
        self._selected_layers = self._get_selected_layers()

    def _get_selected_layers(self):
        """Lê camadas selecionadas de variável de ambiente."""
        env_layers = os.getenv("DATAGEO_SP_LAYERS", "").strip()
        if not env_layers:
            return AVAILABLE_LAYERS

        selected_names = {s.strip() for s in env_layers.split(",") if s.strip()}
        return [cfg for cfg in AVAILABLE_LAYERS if cfg["layer"] in selected_names]

    def extract(self) -> ExtractedData:
        """Extrai dados de múltiplas camadas."""
        all_features = []

        for layer_cfg in self._selected_layers:
            logger.info(f"Fetching layer: {layer_cfg['layer']}")

            request = WFSRequest(
                url=self.data_source.url,
                layer=layer_cfg["layer"],
                wfs_version="2.0.0",
            )

            try:
                gdf = self.wfs_client.fetch_all(request)
                if not gdf.empty:
                    # Adicionar informações de camada
                    gdf["_tema"] = layer_cfg["tema"]
                    gdf["_subtipo"] = layer_cfg["subtipo"]
                    gdf["_id_fields"] = layer_cfg["id_fields"]
                    gdf["_nome_fields"] = layer_cfg["nome_fields"]
                    all_features.extend(gdf.to_dict("records"))
            except Exception as e:
                logger.warning(f"Failed to fetch {layer_cfg['layer']}: {str(e)}")

        if not all_features:
            raise Exception("No features fetched from any DataGeo layer")

        return ExtractedData(
            source=self.data_source,
            rows=all_features,
            metadata={"feature_count": len(all_features), "layers": len(self._selected_layers)},
        )


class DataGeoSPTransformer(GeometricTransformer):
    """Transformador para dados de DataGeo."""

    def __init__(self):
        super().__init__(table_name="camada_estadual_ambiental")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de camada ambiental."""
        props = feature.get("properties", feature)

        # Extrair metadados de camada
        tema = props.pop("_tema", "Camada Ambiental")
        subtipo = props.pop("_subtipo", None)
        id_fields = props.pop("_id_fields", ("id", "gid", "objectid"))
        nome_fields = props.pop("_nome_fields", ("nome", "NOME", "name"))

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
            id_origem=str(self.pick(props, id_fields)),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "tema": tema,
                "subtipo": subtipo,
                "nome": self.pick(props, nome_fields),
                "atributos_json": self.row_to_json(props),
            },
        )


class DataGeoSPLoader(GeometricLoader):
    """Carregador para camadas ambientais."""

    def __init__(self, engine):
        super().__init__(engine, table_name="camada_estadual_ambiental")

    def get_insert_query(self) -> str:
        """Query de inserção para camada_estadual_ambiental."""
        return """
            INSERT INTO camada_estadual_ambiental
                (id, id_origem, dataset_id, tema, subtipo, nome,
                 geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :tema, :subtipo, :nome,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class DataGeoSPPipeline(BasePipeline):
    """Pipeline completa para DataGeo SP."""

    def _get_dataset_name(self) -> str:
        return "DATAGEO_SP_AMBIENTAIS"

    def _get_dataset_description(self) -> str:
        return "Camadas Ambientais do Estado de São Paulo - DataGeo"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de DataGeo SP."""
    extractor = DataGeoSPExtractor(wfs_client)
    transformer = DataGeoSPTransformer()
    loader = DataGeoSPLoader(engine)

    return DataGeoSPPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=DATAGEO_SOURCE,
    )
