"""
Pipeline INPE - Queimadas (Eventos de Fogo)

Fonte: INPE BDQueimadas
Path: database/docs/bdqueimadas_*.csv
Tabela: queimada_evento
Tipo: Pontos (geometria POINT, não MULTIPOLYGON)
"""
import logging
from datetime import datetime, date
from uuid import uuid4

from core.models import ExtractedData, TransformedRecord, DataSource
from etl.extractors import CSVExtractor
from etl.transformers import BaseTransformer
from etl.loaders import BaseLoader
from etl.pipeline import BasePipeline

logger = logging.getLogger(__name__)

# Sentinel para valores nulos em RiscoFogo
_RISCO_NULL = -999.0

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
_BIOMA = ("Bioma", "bioma", "BIOMA", "biome")
_DIAS_SEM_CHUVA = ("DiaSemChuva", "dias_sem_chuva", "DiasSemChuva", "Dias_sem_chuva")
_PRECIPITACAO = ("Precipitacao", "precipitacao", "Precipitação", "precip")
_RISCO_FOGO = ("RiscoFogo", "risco_fogo", "Risco", "RiscoFogo_1km")
_ID_ORIG = ("Latitude", "latitude", "LAT", "lat")  # (lat_lon_data para ID)


class INPEExtractor(CSVExtractor):
    """Extrator para dados de queimadas do INPE."""

    def __init__(self):
        super().__init__(
            INPE_SOURCE,
            csv_pattern="/home/joyce/Documents/fatec/api/DataProcessing-2026-1/models/docs/bdqueimadas_*.csv",
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
                try:
                    data_ocorrencia = datetime.strptime(data_str, "%Y/%m/%d %H:%M:%S")
                except ValueError:
                    # Use current date if parsing fails
                    data_ocorrencia = datetime.now()

                # Criar geometria POINT (não MULTIPOLYGON!)
                geom_wkt = f"POINT({lon} {lat})"

                record = TransformedRecord(
                    id=str(uuid4()),
                    id_origem=f"{lat}_{lon}_{data_str}",
                    table_name=self.table_name,
                    geometry=geom_wkt,
                    attributes={
                        "data_ocorrencia": data_ocorrencia,
                        "fonte_sensor": str(
                            self.pick(row_dict, _SATELITE) or ""
                        ).strip() or None,
                        "intensidade": self.safe_float(self.pick(row_dict, _FRP)),
                        "bioma": str(self.pick(row_dict, _BIOMA) or "").strip() or None,
                        "dias_sem_chuva": self.safe_int(
                            self.pick(row_dict, _DIAS_SEM_CHUVA)
                        ),
                        "precipitacao_mm": self.safe_float(
                            self.pick(row_dict, _PRECIPITACAO),
                            null_sentinel=_RISCO_NULL,
                        ),
                        "risco_fogo": self.safe_float(
                            self.pick(row_dict, _RISCO_FOGO),
                            null_sentinel=_RISCO_NULL,
                        ),
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


class INPELoader(BaseLoader):
    """Carregador para eventos de queimada."""

    def __init__(self, engine):
        super().__init__(engine, table_name="queimada_evento")

    def get_insert_query(self) -> str:
        """Query de inserção para queimada_evento."""
        return """
            INSERT INTO queimada_evento
                (id, id_origem, dataset_id, data_ocorrencia, fonte_sensor,
                 intensidade, bioma, dias_sem_chuva, precipitacao_mm,
                 risco_fogo, geom, atributos_json)
            VALUES
                (:id, :id_origem, :dataset_id, :data_ocorrencia, :fonte_sensor,
                 :intensidade, :bioma, :dias_sem_chuva, :precipitacao_mm,
                 :risco_fogo,
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
