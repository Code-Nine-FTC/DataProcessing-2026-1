"""
Pipeline CAR - Cadastro Ambiental Rural

Fonte: Serviço Florestal Brasileiro via TerraBrasilis
URL: http://terrabrasilis.dpi.inpe.br/geoserver/wfs
Tabela: imovel_rural
Layer: prodes-car:car_properties (WFS 2.0.0)

Nota: Faz lookup de municipio_id a partir de nome e UF durante transformação.
"""
import logging
import os
import re
import zipfile
from datetime import date
from pathlib import Path
from uuid import uuid4

import geopandas as gpd
import requests

from sqlalchemy import text

from core.models import ExtractedData, TransformedRecord, DataSource
from core.crs_handler import standardize_geodataframe
from core.geometry_validator import validate_and_clean_geometries
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest
from infrastructure.repositories import MunicipioRepository
from core.exceptions import ExtractionException

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
_CODIGO_CAR = (
    "codigo_car",
    "CODIGO_CAR",
    "car_code",
    "id_car",
    "codigo",
    "cod_imovel",
)
_AREA = ("area_hectare", "AREA_HECTARE", "area_ha", "area", "num_area")
_SITUACAO = (
    "situacao_imovel",
    "SITUACAO_IMOVEL",
    "status",
    "situacao",
    "ind_status",
    "des_condic",
)
_MUNICIPIO = ("municipio", "MUNICIPIO", "mun_nome", "municipality")
_UF = ("uf", "UF", "estado", "state", "cod_estado")
_ID_ORIG = ("gid", "GID", "id", "car_id", "cod_car", "cod_imovel")
CAR_LAYER = os.getenv("CAR_WFS_LAYER", "prodes-car:car_properties")


class CARExtractor(WFSExtractor):
    """Extrator para Cadastro Ambiental Rural."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(CAR_SOURCE, wfs_client, CAR_LAYER)

    def _published_layers(self) -> list[str]:
        """Retorna layers publicadas no endpoint WFS."""
        capabilities_url = f"{self.data_source.url}?service=WFS&request=GetCapabilities"
        response = requests.get(capabilities_url, timeout=60)
        response.raise_for_status()
        xml = response.text
        matches = re.findall(r"<wfs:Name>([^<]+)</wfs:Name>|<Name>([^<]+)</Name>", xml)
        return [a or b for a, b in matches]

    def _extract_zip_files(self, folder: Path) -> None:
        for root, _, files in os.walk(folder):
            for file_name in files:
                if not file_name.lower().endswith(".zip"):
                    continue
                zip_path = Path(root) / file_name
                logger.info("[CAR fallback] Extracting ZIP: %s", zip_path)
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(root)

    def _find_shapefile(self, folder: Path) -> Path:
        for root, _, files in os.walk(folder):
            for file_name in files:
                if file_name.lower().endswith(".shp"):
                    return Path(root) / file_name
        raise ExtractionException(
            f"Fallback local de CAR não encontrou .shp em: {folder}"
        )

    def _extract_root_data_zip_if_exists(self) -> None:
        """Extrai data.zip na raiz do projeto, se existir."""
        data_zip = Path.cwd() / "data.zip"
        if data_zip.exists():
            logger.info("[CAR fallback] Extracting root archive: %s", data_zip)
            with zipfile.ZipFile(data_zip, "r") as zip_ref:
                zip_ref.extractall(Path.cwd())

    def _resolve_fallback_dir(self) -> Path:
        """Resolve pasta de fallback sem exigir variável de ambiente.

        Ordem:
        1) CAR_LOCAL_FALLBACK_DIR (se definido)
        2) caminhos convencionais no projeto
        """
        env_dir = os.getenv("CAR_LOCAL_FALLBACK_DIR")
        if env_dir:
            candidate = Path(env_dir)
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            return candidate

        conventional_paths = [
            Path.cwd() / "data" / "sicar",
            Path.cwd() / "data" / "sicar" / "SP",
            Path.cwd() / "data" / "data" / "sicar",
        ]

        for candidate in conventional_paths:
            if candidate.exists():
                return candidate

        # Retorna caminho padrão para mensagem de erro objetiva.
        return conventional_paths[0]

    def _extract_from_local_fallback(self) -> ExtractedData:
        self._extract_root_data_zip_if_exists()
        fallback_dir = self._resolve_fallback_dir()

        if not fallback_dir.exists():
            raise ExtractionException(
                "Fallback local de CAR indisponível: pasta não existe. "
                f"Esperado por convenção em: {fallback_dir}. "
                "Opcionalmente, defina CAR_LOCAL_FALLBACK_DIR no .env."
            )

        self._extract_zip_files(fallback_dir)
        shp_path = self._find_shapefile(fallback_dir)
        logger.info("[CAR fallback] Reading shapefile: %s", shp_path)

        gdf = gpd.read_file(shp_path)
        gdf = standardize_geodataframe(gdf)
        gdf = validate_and_clean_geometries(gdf)

        return ExtractedData(
            source=self.data_source,
            rows=gdf.to_dict("records"),
            metadata={
                "feature_count": len(gdf),
                "source": "local_fallback",
                "source_file": str(shp_path),
            },
        )

    def extract(self) -> ExtractedData:
        """Extrai dados de CAR validando previamente se a layer está publicada."""
        try:
            names = self._published_layers()
        except Exception as e:
            logger.warning(
                "Não foi possível consultar GetCapabilities de CAR em %s: %s. "
                "Tentando fallback local (ZIP/SHP).",
                self.data_source.url,
                e,
            )
            return self._extract_from_local_fallback()

        if self.wfs_layer not in names:
            candidates = [
                n for n in names if any(k in n.lower() for k in ("car", "imovel", "sicar"))
            ]
            logger.warning(
                "Layer de CAR não encontrada no endpoint WFS (layer='%s'). "
                "Candidatas encontradas: %s. Tentando fallback local (ZIP/SHP).",
                self.wfs_layer,
                candidates[:10] if candidates else "nenhuma",
            )
            return self._extract_from_local_fallback()

        try:
            return super().extract()
        except Exception as e:
            logger.warning(
                "Falha na extração WFS de CAR: %s. Tentando fallback local (ZIP/SHP).",
                e,
            )
            return self._extract_from_local_fallback()


class CARTransformer(GeometricTransformer):
    """Transformador para dados de imóveis rurais."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__(table_name="imovel_rural")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord:
        """Transforma feature de imóvel rural. Filtra apenas SP."""
        props = feature.get("properties", feature)

        # Filtra apenas SP, igual às outras pipelines
        uf = self.pick(props, _UF)
        if uf and str(uf).upper() != "SP":
            return None

        geometry = feature.get("geometry")
        geom_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom and not geom.is_empty:
                geom_wkt = geom.wkt

        # Descarta registro sem geometria válida (evita violação de NOT NULL em geom/centroid)
        if geom_wkt is None:
            return None

        # Buscar municipio_id
        municipio_nome = self.pick(props, _MUNICIPIO)
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

        nome_imovel = self.pick(props, _NOME)
        if nome_imovel and str(nome_imovel).strip().lower() == "area do imovel":
            nome_imovel = None

        codigo_car = self.pick(props, _CODIGO_CAR)
        if codigo_car is not None:
            codigo_car = str(codigo_car).upper()

        return TransformedRecord(
            id=str(uuid4()),
            id_origem=str(self.pick(props, _ID_ORIG)),
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "nome_imovel": nome_imovel,
                "codigo_car": codigo_car,
                "area_ha": self.safe_float(self.pick(props, _AREA)),
                "municipio_id": municipio_id,
                "situacao_cadastral": self.pick(props, _SITUACAO),
                "atributos_json": self.row_to_json(props),
            },
        )


class CARLoader(GeometricLoader):
    """Carregador para imóveis rurais."""

    def __init__(self, engine):
        super().__init__(engine, table_name="imovel_rural")

    def get_insert_query(self) -> str:
        """Query de inserção para imovel_rural.
        centroid é derivado da geometria no banco para garantir NOT NULL.
        """
        return """
            INSERT INTO imovel_rural
                (id, id_origem, dataset_id, nome_imovel, codigo_car,
                 area_ha, municipio_id, situacao_cadastral, geom, centroid, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :nome_imovel, :codigo_car,
                 :area_ha, :municipio_id, :situacao_cadastral,
                 ST_GeomFromText(:geom_wkt, 4326),
                 ST_PointOnSurface(ST_GeomFromText(:geom_wkt, 4326)),
                 CAST(:atributos_json AS JSONB))
        """


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
