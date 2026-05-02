"""
Pipeline PRODES Mata Atlântica - Desmatamento SP

Fonte: TerraBrasilis WFS (INPE)
URL: http://terrabrasilis.dpi.inpe.br/geoserver/wfs
Camada: prodes-mata-atlantica-nb:yearly_deforestation
Tabela: desmatamento_alerta
Filtro: state = 'São Paulo'
"""
import logging
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import text

from core.models import ExtractedData, TransformedRecord, DataSource, LoadResult
from etl.extractors import WFSExtractor
from etl.transformers import GeometricTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline
from infrastructure.wfs_client import WFSClient, WFSRequest
from infrastructure.repositories import MunicipioRepository

logger = logging.getLogger(__name__)

PRODES_SOURCE = DataSource(
    name="PRODES Mata Atlântica - Desmatamento SP",
    url="http://terrabrasilis.dpi.inpe.br/geoserver/wfs",
    format="WFS/GeoJSON",
    agency="Instituto Nacional de Pesquisas Espaciais",
    scope="estadual",
    frequency="anual",
    license="CC BY 4.0",
)

_WFS_LAYER = "prodes-mata-atlantica-nb:yearly_deforestation"
_STATE_FILTER = "state='SP'"

# Candidatos de nomes de colunas (a API PRODES pode variar entre versões)
_GID = ("gid", "GID", "fid", "FID", "objectid", "id", "ID")
_STATE = ("state", "STATE", "estado", "ESTADO", "uf", "UF")
_YEAR = ("year", "YEAR", "ano", "ANO")
_IMAGE_DATE = ("image_date", "IMAGE_DATE", "data_imagem", "date", "DATA", "data")
_CLASS_NAME = ("class_name", "CLASS_NAME", "classname", "main_class", "MAIN_CLASS", "classe")
_AREA_KM = ("areamunkm", "AREAMUNKM", "area_km", "areakm2", "area_km2", "area_ha_mun")
_AREA_M2 = ("areameters", "AREAMETERS", "area_m2", "area_metros")
_MUNICIPIO = ("municipio", "MUNICIPIO", "city", "municipality", "mun_nome", "nome_municipio")


def _link_desmatamento_to_municipios(engine, dataset_id: str | None = None) -> None:
    """Preenche desmatamento_alerta.municipio_id via ST_Intersects com municípios de SP."""
    ds_clause = ""
    params: dict = {}
    if dataset_id:
        ds_clause = " AND da.dataset_id = CAST(:ds AS uuid)"
        params["ds"] = str(dataset_id)

    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"""
                WITH ranked AS (
                  SELECT
                    da.id AS da_id,
                    m.id AS mun_id,
                    ROW_NUMBER() OVER (
                      PARTITION BY da.id
                      ORDER BY ST_Area(ST_Intersection(m.geom, da.geom)) DESC, m.nome ASC
                    ) AS rn
                  FROM desmatamento_alerta da
                  INNER JOIN municipio m ON ST_Intersects(m.geom, da.geom)
                  INNER JOIN estado e ON e.id = m.estado_id AND UPPER(e.sigla) = 'SP'
                  WHERE da.municipio_id IS NULL
                  {ds_clause}
                ),
                matched AS (
                  SELECT da_id, mun_id FROM ranked WHERE rn = 1
                )
                UPDATE desmatamento_alerta da
                SET municipio_id = matched.mun_id
                FROM matched
                WHERE da.id = matched.da_id
                """
            ),
            params,
        )

    logger.info(
        "desmatamento_alerta: municipio_id atualizados via spatial join — %s registros",
        getattr(result, "rowcount", -1),
    )


class PRODESExtractor(WFSExtractor):
    """Extrator para dados de desmatamento PRODES Mata Atlântica - filtra São Paulo."""

    def __init__(self, wfs_client: WFSClient):
        super().__init__(PRODES_SOURCE, wfs_client, _WFS_LAYER)

    def extract(self) -> ExtractedData:
        logger.info("Buscando PRODES Mata Atlântica yearly_deforestation para São Paulo...")
        request = WFSRequest(
            url=PRODES_SOURCE.url,
            layer=_WFS_LAYER,
            wfs_version="2.0.0",
            paginate=True,
            batch_size=500,
            cql_filter=_STATE_FILTER,
        )
        gdf = self.wfs_client.fetch_all(request)

        if gdf.empty:
            from core.exceptions import ExtractionException
            raise ExtractionException(
                "Nenhuma feature obtida da camada PRODES Mata Atlântica. "
                "Verifique conectividade com http://terrabrasilis.dpi.inpe.br"
            )

        rows = gdf.to_dict("records")
        logger.info("PRODES SP: %d features obtidas", len(rows))
        return ExtractedData(
            source=PRODES_SOURCE,
            rows=rows,
            metadata={"feature_count": len(rows), "layer": _WFS_LAYER},
        )


class PRODESTransformer(GeometricTransformer):
    """Transformador para alertas de desmatamento PRODES."""

    def __init__(self, municipio_repo: MunicipioRepository):
        super().__init__("desmatamento_alerta")
        self.municipio_repo = municipio_repo

    def transform_feature(self, feature: dict) -> TransformedRecord | None:
        props = feature.get("properties", feature)

        # vai descartar caso seja diferente de sp mesmo que o filtro falhe
        state_val = str(self.pick(props, _STATE) or "").strip().upper()
        if state_val and state_val not in ("SÃO PAULO", "SAO PAULO", "SP", ""):
            return None

        geometry = feature.get("geometry")
        geom_wkt = None
        if geometry:
            from shapely.geometry import shape
            geom = shape(geometry)
            geom = self.ensure_multipolygon(geom)
            if geom:
                geom_wkt = geom.wkt

        if not geom_wkt:
            return None

        area_km = self.safe_float(self.pick(props, _AREA_KM))
        area_m2 = self.safe_float(self.pick(props, _AREA_M2))
        if area_km is not None:
            area_ha = area_km * 100.0
        elif area_m2 is not None:
            area_ha = area_m2 / 10_000.0
        else:
            area_ha = None

        data_ocorrencia = None
        image_date_raw = self.pick(props, _IMAGE_DATE)
        if image_date_raw:
            try:
                data_ocorrencia = datetime.strptime(str(image_date_raw)[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        if data_ocorrencia is None:
            year_raw = self.pick(props, _YEAR)
            if year_raw:
                try:
                    data_ocorrencia = date(int(year_raw), 12, 31)
                except (ValueError, TypeError):
                    pass

        class_name = str(self.pick(props, _CLASS_NAME) or "DESMATAMENTO").strip()

        municipio_nome = self.pick(props, _MUNICIPIO)
        municipio_id = None
        if municipio_nome:
            try:
                municipio_id = self.municipio_repo.find_by_name_and_state(
                    str(municipio_nome), "SP"
                )
            except Exception as e:
                logger.debug("Município não encontrado '%s': %s", municipio_nome, e)

        gid = self.pick(props, _GID)
        id_origem = f"PRODES_MA_{gid}" if gid is not None else f"PRODES_MA_{uuid4().hex[:12]}"

        return TransformedRecord(
            id=str(uuid4()),
            id_origem=id_origem,
            table_name=self.table_name,
            geometry=geom_wkt,
            attributes={
                "data_ocorrencia": data_ocorrencia,
                "tipo_alerta": class_name,
                "area_ha": area_ha,
                "municipio_id": municipio_id,
                "atributos_json": self.row_to_json(props),
            },
        )


class PRODESLoader(GeometricLoader):
    """Carregador para desmatamento_alerta."""

    def __init__(self, engine):
        super().__init__(engine, table_name="desmatamento_alerta")

    def load(self, records, dataset_id: str) -> LoadResult:
        result = super().load(records, dataset_id)
        if result.inserted_records > 0:
            try:
                _link_desmatamento_to_municipios(self.engine, dataset_id)
            except Exception as e:
                logger.warning("Falha ao vincular desmatamentos a municípios: %s", e)
        return result

    def get_insert_query(self) -> str:
        return """
            INSERT INTO desmatamento_alerta
                (id, id_origem, dataset_id, data_ocorrencia, tipo_alerta,
                 area_ha, municipio_id, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :data_ocorrencia, :tipo_alerta,
                 :area_ha, :municipio_id,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class PRODESPipeline(BasePipeline):
    """Pipeline completa para PRODES Desmatamento SP."""

    def _get_dataset_name(self) -> str:
        return f"PRODES_Desmatamento_SP_{date.today().year}"

    def _get_dataset_description(self) -> str:
        return "Desmatamento anual em São Paulo - PRODES Mata Atlântica (TerraBrasilis/INPE)"


def create_pipeline(engine, wfs_client: WFSClient):
    """Factory para criar pipeline PRODES Desmatamento SP."""
    municipio_repo = MunicipioRepository(engine)
    extractor = PRODESExtractor(wfs_client)
    transformer = PRODESTransformer(municipio_repo)
    loader = PRODESLoader(engine)

    return PRODESPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=PRODES_SOURCE,
    )
