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
from infrastructure.repositories import MunicipioRepository

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
_MUNICIPIO = ("municipio", "MUNICIPIO", "mun_nome", "nm_municipio")
_UF_SIGLA = ("uf", "UF", "sigla_uf", "SIGLA_UF", "estado")
_AREA_HA = ("area_ha", "AREA_HA", "area", "AREA", "area_km2", "AREA_KM2") # Não disponível nesta fonte, mas mantido para consistência


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
        failed_layers = []

        for layer in BIOME_LAYERS:
            logger.info(f"Fetching biome layer: {layer}")
            self.wfs_layer = layer
            try:
                gdf = self.wfs_client.fetch_all(
                    self._create_wfs_request(), deduplicate_by="gid"
                )
                all_features.extend(gdf.to_dict("records"))
                logger.info(f"  → {len(gdf)} features")
            except Exception as e:
                logger.warning(f"Failed to fetch {layer}: {str(e)}")
                failed_layers.append(layer)

        if failed_layers:
            logger.error(
                "Falha em %d/%d camadas ICMBio: %s",
                len(failed_layers), len(BIOME_LAYERS), failed_layers,
            )

        if not all_features:
            from core.exceptions import ExtractionException
            raise ExtractionException(
                f"Nenhuma feature obtida do TerraBrasilis WFS. "
                f"Todas as {len(BIOME_LAYERS)} camadas falharam: {failed_layers}. "
                "Verifique conectividade com http://terrabrasilis.dpi.inpe.br"
            )

        seen_ids = set()
        deduped = []
        skipped_none = 0
        for feature in all_features:
            id_orig = _pick(feature, _ID_ORIG) or feature.get("properties", {}).get("gid")
            if id_orig is None:
                skipped_none += 1
                continue
            if id_orig not in seen_ids:
                seen_ids.add(id_orig)
                deduped.append(feature)

        if skipped_none:
            logger.warning(f"{skipped_none} features descartadas por id_orig nulo.")

        logger.info(
            f"UC deduplication: {len(all_features)} → {len(deduped)} "
            f"(removed {len(all_features) - len(deduped)})"
        )
        data = ExtractedData(
            source=ICMBIO_SOURCE,
            rows=deduped,
            metadata={"feature_count": len(deduped), "biome_layers": len(BIOME_LAYERS)},
        )

        self.save_data(data=data, path="output")

        return data

    def _create_wfs_request(self):
        """Cria request WFS para camada atual."""
        from infrastructure.wfs_client import WFSRequest
        return WFSRequest(
            url=ICMBIO_SOURCE.url,
            layer=self.wfs_layer,
            wfs_version="1.1.0",
            paginate=False,
            batch_size=10000,
        )


class ICMBioTransformer(GeometricTransformer):
    """Transformador para dados de ICMBio ajustado para calcular área e buscar município."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="unidade_conservacao")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma uma feature de UC."""
        # GeoJSON pode vir como properties ou como fields diretos
        props = feature.get("properties", feature)

        uf = self.pick(props, _UF_SIGLA)

        geometry = feature.get("geometry")
        
        # 1. Tratamento da Geometria
        geom_wkt = None
        area_calculada = 0.0
        
        if geometry:
            from shapely.geometry import shape
            import shapely.ops as ops
            from functools import partial
            import pyproj
            
            geom = shape(geometry)
            if not geom.is_valid:
                geom = geom.buffer(0)
            
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt
                
                # 2. CÁLCULO DA ÁREA (Já que não vem no GeoJSON)
                # Projeta para um sistema métrico (Web Mercator) para calcular área em m2
                proj_transform = partial(
                    pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True).transform
                )
                geom_projetada = ops.transform(proj_transform, geom)
                area_calculada = geom_projetada.area / 10000  # Converte m² para Hectares

        # 3. BUSCA DO MUNICÍPIO POR GEOMETRIA
        municipio_id = None
        if geom_wkt:
            try:
                municipio_id = self.municipio_repo.find_by_geometry(geom_wkt)
            except Exception as e:
                logger.warning(f"Não foi possível encontrar município via espacial: {str(e)}")

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
                "area_ha": area_calculada,  # Não disponível nesta fonte
                "municipio_id": municipio_id,
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
                 grupo_snuc, area_ha, municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome, :categoria, :esfera,
                 :grupo_snuc, :area_ha, :municipio_id,
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
    municipio_repo = MunicipioRepository(engine)
    extractor = ICMBioExtractor(wfs_client)
    transformer = ICMBioTransformer(municipio_repo)
    loader = ICMBioLoader(engine)

    return ICMBioPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=ICMBIO_SOURCE,
    )
