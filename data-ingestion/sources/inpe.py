"""
ETL: Queimadas — INPE / BDQueimadas
Fonte:  CSV local em database/docs/bdqueimadas_*.csv
Tabela: queimada_evento

Pré-requisito: rodar 'alembic upgrade head' para adicionar as colunas
bioma, dias_sem_chuva, precipitacao_mm e risco_fogo à tabela.
"""
import glob
import os
import sys
import uuid
from datetime import date, datetime

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, ".")
sys.path.insert(0, "data-ingestion")
from models.database import get_engine
from loader import get_or_create_fonte_dado, get_or_create_dataset
from utils import safe_float, safe_int

CSV_GLOB = "database/docs/bdqueimadas_*.csv"

FONTE = {
    "nome": "INPE - BDQueimadas",
    "orgao_responsavel": "Instituto Nacional de Pesquisas Espaciais",
    "url_origem": "https://queimadas.dgi.inpe.br/queimadas/bdqueimadas",
    "formato": "CSV",
    "periodicidade": "diária",
    "escopo_geografico": "nacional",
    "licenca": "Dados Abertos Gov",
}

# RiscoFogo usa -999 como sentinel de valor nulo
_RISCO_NULL = -999.0

# Candidatos de nomes de colunas do CSV (varia entre versões do BDQueimadas)
_LAT            = ("Latitude", "latitude", "LAT", "lat")
_LON            = ("Longitude", "longitude", "LON", "lon")
_DATAHORA       = ("DataHora", "data_hora", "DataHora_GMT", "Data")
_SATELITE       = ("Satelite", "satelite", "Satélite", "SATELITE", "satellite")
_FRP            = ("FRP", "frp", "Frp", "potencia")
_BIOMA          = ("Bioma", "bioma", "BIOMA", "biome")
_DIAS_SEM_CHUVA = ("DiaSemChuva", "dias_sem_chuva", "DiasSemChuva", "Dias_sem_chuva")
_PRECIPITACAO   = ("Precipitacao", "precipitacao", "Precipitação", "precip")
_RISCO_FOGO     = ("RiscoFogo", "risco_fogo", "Risco", "RiscoFogo_1km")


def _find_csv() -> str | None:
    files = sorted(glob.glob(CSV_GLOB))
    return files[-1] if files else None


def run():
    print("[inpe] Iniciando ETL...")
    csv_path = _find_csv()
    if not csv_path:
        print(f"[inpe] Nenhum CSV encontrado em '{CSV_GLOB}'. Coloque o arquivo em database/docs/.")
        return

    print(f"[inpe] Lendo: {csv_path}")
    df = pd.read_csv(csv_path, encoding="latin-1")
    df.columns = df.columns.str.strip()

    # Prepara rows antes de abrir transação
    print(f"[inpe] {len(df)} linhas. Preparando inserção...")
    rows = []
    skipped = 0

    for _, row in df.iterrows():
        lat_raw = pick(row, _LAT)
        lon_raw = pick(row, _LON)
        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except (TypeError, ValueError):
            skipped += 1
            continue

        data_str = str(pick(row, _DATAHORA) or "").strip()
        try:
            data_ocorrencia = datetime.strptime(data_str, "%Y/%m/%d %H:%M:%S")
        except ValueError:
            data_ocorrencia = None

        rows.append({
            "id": str(uuid.uuid4()),
            "id_origem": f"{lat}_{lon}_{data_str}",
            "dataset_id": None,  # preenchido após criar dataset
            "data_ocorrencia": data_ocorrencia,
            "fonte_sensor": str(pick(row, _SATELITE) or "").strip() or None,
            "intensidade": safe_float(pick(row, _FRP)),
            "bioma": str(pick(row, _BIOMA) or "").strip() or None,
            "dias_sem_chuva": safe_int(pick(row, _DIAS_SEM_CHUVA)),
            "precipitacao_mm": safe_float(pick(row, _PRECIPITACAO), null_sentinel=_RISCO_NULL),
            "risco_fogo": safe_float(pick(row, _RISCO_FOGO), null_sentinel=_RISCO_NULL),
            "geom_wkt": f"POINT({lon} {lat})",
        })

    if skipped:
        print(f"[inpe] {skipped} linhas ignoradas (sem coordenadas válidas).")

    dataset_nome = f"INPE_Queimadas_{os.path.basename(csv_path)}"
    engine = get_engine()

    # Tudo numa única transação — se o INSERT falhar, dataset não é commitado
    with engine.begin() as conn:
        fonte_id = get_or_create_fonte_dado(conn, **FONTE)
        dataset_id, is_new = get_or_create_dataset(
            conn,
            fonte_id,
            nome=dataset_nome,
            descricao=f"Focos de queimada importados de {os.path.basename(csv_path)}",
            versao=str(date.today().year),
            data_referencia=date.today(),
        )

        if not is_new:
            return

        for r in rows:
            r["dataset_id"] = dataset_id

        conn.execute(
            text("""
                INSERT INTO queimada_evento
                    (id, id_origem, dataset_id, data_ocorrencia, fonte_sensor,
                     intensidade, bioma, dias_sem_chuva, precipitacao_mm,
                     risco_fogo, geom)
                VALUES
                    (:id, :id_origem, :dataset_id, :data_ocorrencia, :fonte_sensor,
                     :intensidade, :bioma, :dias_sem_chuva, :precipitacao_mm,
                     :risco_fogo,
                     ST_GeomFromText(:geom_wkt, 4326))
            """),
            rows,
        )

    print(f"[inpe] {len(rows)} registros inseridos.")


if __name__ == "__main__":
    run()
