"""
Pipeline ICMBio - Unidades de Conservação

Fonte: TerraBrasilis WFS (INPE)
URL: http://terrabrasilis.dpi.inpe.br/geoserver/wfs
Tabela: unidade_conservacao

Implementação do padrão ETL com separação de responsabilidades.
"""
import logging
from uuid import uuid4
from datetime import date

from sqlalchemy import text

from core.models import ExtractedData, TransformedRecord, DataSource
from core.config import WFSConfig
from domain.entities import UnidadeConservacao
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient

logger = logging.getLogger(__name__)

# Configuração da fonte
ICMBIO_SOURCE = DataSource(
    name="ICMBio - Unidades de Conservação",
    url="http://terrabrasilis.dpi.inpe.br/geoserver/wfs",
    format="WFS/GeoJSON",
    agency="Instituto Chico Mendes de Conservação da Biodiversidade",
    scope="nacional",
    frequency="anual",
    license="CC BY 4.0",
)

# Camadas de UC por bioma (TerraBrasilis)
BIOME_LAYERS = [
    "prodes-amazon-nb:conservation_units_amazon_biome",
    "prodes-cerrado-nb:conservation_units_cerrado_biome",
    "prodes-mata-atlantica-nb:conservation_units_mata_atlantica_biome",
    "prodes-caatinga-nb:conservation_units_caatinga_biome",
    "prodes-pampa-nb:conservation_units_pampa_biome",
    "prodes-pantanal-nb:conservation_units_pantanal_biome",
]

# Candidatos de nomes de colunas
_NOME = ("nome", "NOME", "nm_uc", "NM_UC", "nome_uc", "name")
_CATEGORIA = ("categoria", "CATEGORIA", "cat", "CAT_UC", "nome_cat")
_ESFERA = ("esfera", "ESFERA", "esfera_gov", "ESFERA_GOV")
_GRUPO = ("grupo", "GRUPO", "grupo_uc", "GRUPO_STATUS", "DS_GRUPO_STATUS")
_ID_ORIG = ("id", "ID", "gid", "FID", "objectid", "cod_uc")


def _pick(record: dict, candidates: tuple, default=None):
    """Retorna o primeiro valor não-nulo de uma lista de candidatos."""
    for candidate in candidates:
        if candidate not in record:
            continue
        v = record.get(candidate)
        if v is not None and str(v).strip() not in ("", "nan", "None"):
            return v
    return default


class ICMBioExtractor(WFSExtractor):
    """Extrator específico para ICMBio - busca múltiplas camadas de biomas."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(ICMBIO_SOURCE, wfs_client, "")

    def extract(self) -> ExtractedData:
        """Busca todas as UCs de todos os biomas."""
        all_features = []
        total_dedup = 0

        for layer in BIOME_LAYERS:
            logger.info(f"Fetching biome layer: {layer}")
            self.wfs_layer = layer
            try:
                gdf = self.wfs_client.fetch_all(
                    self._create_wfs_request(), deduplicate_by="id"
                )
                all_features.extend(gdf.to_dict("records"))
                logger.info(f"  → {len(gdf)} features")
            except Exception as e:
                logger.warning(f"Failed to fetch {layer}: {str(e)}")

        if not all_features:
            raise Exception("No features fetched from any biome layer")

        # Deduplicar por ID origem (mesma UC pode estar em múltiplos biomas)
        seen_ids = set()
        deduped = []
        for feature in all_features:
            id_orig = _pick(feature, _ID_ORIG, feature.get("properties", {}).get("gid"))
            if id_orig not in seen_ids:
                seen_ids.add(id_orig)
                deduped.append(feature)

        logger.info(
            f"UC deduplication: {len(all_features)} → {len(deduped)} "
            f"(removed {len(all_features) - len(deduped)})"
        )

        return ExtractedData(
            source=ICMBIO_SOURCE,
            rows=deduped,
            metadata={"feature_count": len(deduped), "biome_layers": len(BIOME_LAYERS)},
        )

    def _create_wfs_request(self):
        """Cria request WFS para camada atual."""
        from infrastructure.wfs_client import WFSRequest
        return WFSRequest(
            url=ICMBIO_SOURCE.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",
        )


class ICMBioTransformer(GeometricTransformer):
    """Transformador para dados de ICMBio."""

    def __init__(self):
        super().__init__(table_name="unidade_conservacao")

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma uma feature de UC."""
        # GeoJSON pode vir como properties ou como fields diretos
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
                "categoria": self.pick(props, _CATEGORIA),
                "esfera": self.pick(props, _ESFERA),
                "grupo_snuc": self.pick(props, _GRUPO),
                "area_ha": None,  # Não disponível nesta fonte
                "atributos_json": self.row_to_json(props),
            },
        )


class ICMBioLoader(GeometricLoader):
    """Carregador para dados de ICMBio."""

    def __init__(self, engine):
        super().__init__(engine, table_name="unidade_conservacao")

    def get_insert_query(self) -> str:
        """Query de inserção para UC."""
        return """
            INSERT INTO unidade_conservacao
                (id, id_origem, dataset_id, nome, categoria, esfera,
                 grupo_snuc, area_ha, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :categoria, :esfera,
                 :grupo_snuc, :area_ha,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class ICMBioPipeline(BasePipeline):
    """Pipeline completa para ICMBio."""

    def _get_dataset_name(self) -> str:
        return "UC_TERRABRASILIS"

    def _get_dataset_description(self) -> str:
        return "Unidades de Conservação do Brasil - TerraBrasilis/INPE"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline de ICMBio."""
    extractor = ICMBioExtractor(wfs_client)
    transformer = ICMBioTransformer()
    loader = ICMBioLoader(engine)

    return ICMBioPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=ICMBIO_SOURCE,
    )
