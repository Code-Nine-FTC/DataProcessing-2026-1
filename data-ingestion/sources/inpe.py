"""
Pipeline INPE - Queimadas (Eventos de Fogo)

Fonte: INPE BDQueimadas
Path: database/docs/bdqueimadas_*.csv
Tabela: queimada_evento
Tipo: Pontos (geometria POINT, não MULTIPOLYGON)
"""
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import text

from core.models import ExtractedData, TransformedRecord, DataSource, LoadResult
from etl.extractors import CSVExtractor
from etl.transformers import BaseTransformer
from etl.loaders import GeometricLoader
from etl.pipeline import BasePipeline

logger = logging.getLogger(__name__)


def link_queimadas_to_municipios(engine, dataset_id: Optional[str] = None) -> None:
    """
    Preenche queimada_evento.municipio_id:
    1) ST_Contains(municipio.geom, ponto) quando geometrias de município existem;
    2) fallback por nome (atributos_json Municipio + Estado, como no CSV INPE).
    """
    ds_clause = ""
    params: dict = {}
    if dataset_id:
        ds_clause = " AND qe.dataset_id = CAST(:ds AS uuid)"
        params["ds"] = dataset_id

    with engine.begin() as conn:
        r1 = conn.execute(
            text(
                f"""
            WITH matched AS (
              SELECT DISTINCT ON (qe.id) qe.id AS qe_id, m.id AS mun_id
              FROM queimada_evento qe
              INNER JOIN municipio m ON ST_Contains(m.geom, qe.geom)
              WHERE qe.municipio_id IS NULL
              {ds_clause}
              ORDER BY qe.id, m.id
            )
            UPDATE queimada_evento qe
            SET municipio_id = matched.mun_id
            FROM matched
            WHERE qe.id = matched.qe_id
            """
            ),
            params,
        )
        r2 = conn.execute(
            text(
                f"""
            UPDATE queimada_evento qe
            SET municipio_id = m.id
            FROM municipio m
            INNER JOIN estado e ON e.id = m.estado_id
            WHERE qe.municipio_id IS NULL
            {ds_clause}
            AND LENGTH(TRIM(COALESCE(qe.atributos_json->>'Municipio', ''))) > 0
            AND UPPER(TRIM(m.nome)) = UPPER(TRIM(qe.atributos_json->>'Municipio'))
            AND (
              UPPER(TRIM(COALESCE(e.nome, '')))
                = UPPER(TRIM(COALESCE(qe.atributos_json->>'Estado', '')))
              OR (
                LENGTH(TRIM(COALESCE(qe.atributos_json->>'Estado', ''))) = 2
                AND UPPER(TRIM(COALESCE(e.sigla, '')))
                  = UPPER(TRIM(COALESCE(qe.atributos_json->>'Estado', '')))
              )
            )
            """
            ),
            params,
        )

    logger.info(
        "queimada_evento: municipio_id atualizados — por geometria: %s, por nome (CSV): %s",
        getattr(r1, "rowcount", -1),
        getattr(r2, "rowcount", -1),
    )


INPE_SOURCE = DataSource(
    name="INPE - BDQueimadas",
    url="https://queimadas.dgi.inpe.br/queimadas/bdqueimadas",
    format="CSV",
    agency="Instituto Nacional de Pesquisas Espaciais",
    scope="nacional",
    frequency="diária",
    license="Dados Abertos Gov",
)

# Candidatos de nomes de colunas (variam entre versões)
_LAT = ("Latitude", "latitude", "LAT", "lat")
_LON = ("Longitude", "longitude", "LON", "lon")
_DATAHORA = ("DataHora", "data_hora", "DataHora_GMT", "Data")
_SATELITE = ("Satelite", "satelite", "Satélite", "SATELITE", "satellite")
_FRP = ("FRP", "frp", "Frp", "potencia")
_BIOMA = ("Bioma", "bioma", "BIOMA")
_DIASEMCHUVA = ("DiaSemChuva", "diasemchuva", "dias_sem_chuva")
_PRECIPITACAO = ("Precipitacao", "precipitacao", "precipitacao_mm")
_RISCOFOGO = ("RiscoFogo", "riscofogo", "risco_fogo")


class INPEExtractor(CSVExtractor):
    """Extrator para dados de queimadas do INPE."""

    def __init__(self):
        _csv_dir = Path(__file__).parents[2] / "models" / "docs"
        super().__init__(
            INPE_SOURCE,
            csv_pattern=str(_csv_dir / "bdqueimadas_*.csv"),
        )


class INPETransformer(BaseTransformer):
    """Transformador para eventos de queimada (pontos)."""

    def __init__(self):
        super().__init__("queimada_evento")

    def transform(self, data: ExtractedData):
        """Transforma registros CSV de queimadas."""
        records = []
        skipped = 0

        for row_dict in data.rows:
            try:
                # Extrair e validar coordenadas
                lat_raw = self.pick(row_dict, _LAT)
                lon_raw = self.pick(row_dict, _LON)

                try:
                    lat = float(lat_raw)
                    lon = float(lon_raw)
                except (TypeError, ValueError):
                    skipped += 1
                    continue

                # Extrair data e hora
                data_str = str(self.pick(row_dict, _DATAHORA) or "").strip()
                data_ocorrencia = None
                if data_str:
                    try:
                        data_ocorrencia = datetime.strptime(data_str, "%Y/%m/%d %H:%M:%S")
                    except ValueError:
                        logger.warning(f"Data inválida ignorada: '{data_str}'")

                # Criar geometria POINT (não MULTIPOLYGON!)
                geom_wkt = f"POINT({lon} {lat})"

                record = TransformedRecord(
                    id=str(uuid4()),
                    id_origem=f"{lat}_{lon}_{data_str}_{str(uuid4())[:8]}",
                    table_name=self.table_name,
                    geometry=geom_wkt,
                    attributes={
                        "data_ocorrencia": data_ocorrencia,
                        "fonte_sensor": str(
                            self.pick(row_dict, _SATELITE) or ""
                        ).strip() or None,
                        "intensidade": self.safe_float(self.pick(row_dict, _FRP)),
                        "bioma": str(self.pick(row_dict, _BIOMA) or "").strip() or None,
                        "dias_sem_chuva": self.safe_int(self.pick(row_dict, _DIASEMCHUVA)),
                        "precipitacao_mm": self.safe_float(self.pick(row_dict, _PRECIPITACAO)),
                        "risco_fogo": self.safe_float(self.pick(row_dict, _RISCOFOGO)),
                        # Demais colunas do CSV ficam em atributos_json (schema atual
                        # só expõe data_ocorrencia, fonte_sensor, intensidade além de geom).
                        "atributos_json": self.row_to_json(row_dict),
                    },
                )
                records.append(record)

            except Exception as e:
                logger.warning(f"Failed to transform row: {str(e)}")
                skipped += 1

        if skipped > 0:
            logger.info(f"Skipped {skipped} invalid rows")

        return records


class INPELoader(GeometricLoader):
    """Carregador para eventos de queimada (usa merge de atributos + WKT como GeometricLoader)."""

    def __init__(self, engine):
        super().__init__(engine, table_name="queimada_evento")

    def load(self, records, dataset_id: str) -> LoadResult:
        result = super().load(records, dataset_id)
        if result.inserted_records > 0:
            try:
                link_queimadas_to_municipios(self.engine, dataset_id)
            except Exception as e:
                logger.warning(
                    "Falha ao vincular queimadas a municípios após carga: %s", e
                )
        return result

    def get_insert_query(self) -> str:
        """Query de inserção para queimada_evento."""
        return """
            INSERT INTO queimada_evento
                (id, id_origem, dataset_id, data_ocorrencia, fonte_sensor,
                 intensidade, bioma, dias_sem_chuva, precipitacao_mm, risco_fogo,
                 geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :data_ocorrencia, :fonte_sensor,
                 :intensidade, :bioma, :dias_sem_chuva, :precipitacao_mm, :risco_fogo,
                 ST_GeomFromText(:geom_wkt, 4326),
                 CAST(:atributos_json AS JSONB))
        """


class INPEPipeline(BasePipeline):
    """Pipeline completa para INPE."""

    def _get_dataset_name(self) -> str:
        return f"INPE_Queimadas_{date.today().year}"

    def _get_dataset_description(self) -> str:
        return "Focos de queimada detectados - INPE BDQueimadas"


def create_pipeline(engine, wfs_client=None):
    """Factory para criar pipeline de INPE."""
    # INPE não usa WFS, mas assinatura é mantida para consistency
    extractor = INPEExtractor()
    transformer = INPETransformer()
    loader = INPELoader(engine)

    return INPEPipeline(
        extractor=extractor,
        transformer=transformer,
        loader=loader,
        fonte_dado=INPE_SOURCE,
    )
