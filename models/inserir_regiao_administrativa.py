"""inserir_regiao_administrativa.py

Pipeline ETL para popular as tabelas `regiao_administrativa` e vincular
cada município paulista à sua RA via `municipio.regiao_administrativa_id`.

Ordem de execução:
  1. inserir_regioes  — cria os 16 registros em regiao_administrativa
  2. vincular_municipios — atualiza municipio.regiao_administrativa_id
  3. calcular_geometrias — faz ST_Union das geometrias dos municípios por RA

Pré-requisito: pipeline inserir_estado_municipio já executada (tabelas
`estado` e `municipio` populadas).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.config.settings import settings
from models.db_model import Estado, Municipio, RegiaoAdministrativa
from models.inserir_estado_municipio import normalizar
from models.regioes_administrativas_sp_data import MUNICIPIO_TO_RA, RA_METADATA

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

SIGLA_UF = "SP"


# ---------------------------------------------------------------------------
# Etapa 1 — Inserir / garantir as 16 RAs
# ---------------------------------------------------------------------------

def inserir_regioes(session, estado_id: int) -> dict[str, int]:
    """Insere (ou confirma existência de) cada RA em RA_METADATA.

    Retorna {nome_normalizado_ra: ra_id}.
    """
    print("[Load] Verificando/inserindo Regiões Administrativas...")
    mapa: dict[str, int] = {}

    for meta in RA_METADATA:
        nome      = meta["nome"]
        nome_norm = normalizar(nome)

        ra = session.query(RegiaoAdministrativa).filter_by(nome=nome).first()

        if ra is None:
            ra = RegiaoAdministrativa(
                nome=nome,
                nome_normalizado=nome_norm,
                sigla=meta["sigla"],
                tipo=meta["tipo"],
                estado_id=estado_id,
            )
            session.add(ra)
            session.flush()          # precisa de ra.id antes do commit
            print(f"  + {meta['sigla']:8s}  {nome}")
        else:
            print(f"  = {meta['sigla']:8s}  {nome}  (id={ra.id}, já existe)")

        mapa[nome_norm] = ra.id

    session.commit()
    print(f"[Load] {len(mapa)} RAs prontas.\n")
    return mapa


# ---------------------------------------------------------------------------
# Etapa 2 — Vincular municípios às RAs
# ---------------------------------------------------------------------------

def vincular_municipios(session, mapa_ra: dict[str, int]) -> dict[int, list[int]]:
    """Atualiza municipio.regiao_administrativa_id para todos os municípios SP.

    Retorna {ra_id: [municipio_id, ...]} para a etapa de geometrias.
    """
    print("[Load] Vinculando municípios às RAs...")

    municipios_por_ra: dict[int, list[int]] = defaultdict(list)
    nao_encontrados: list[str]  = []   # municípios ausentes na tabela municipio
    ra_inexistente:  list[str]  = []   # RAs referenciadas mas não em mapa_ra

    for nome_mun, nome_ra in MUNICIPIO_TO_RA.items():
        nome_ra_norm  = normalizar(nome_ra)
        nome_mun_norm = normalizar(nome_mun)

        ra_id = mapa_ra.get(nome_ra_norm)
        if ra_id is None:
            ra_inexistente.append(f"{nome_mun} → {nome_ra}")
            continue

        mun = (
            session.query(Municipio)
            .filter(Municipio.nome_normalizado == nome_mun_norm)
            .first()
        )
        if mun is None:
            nao_encontrados.append(nome_mun)
            continue

        mun.regiao_administrativa_id = ra_id
        municipios_por_ra[ra_id].append(mun.id)

    session.commit()

    total = sum(len(v) for v in municipios_por_ra.values())
    print(f"[Load] {total} municípios vinculados a {len(municipios_por_ra)} RAs.")

    if nao_encontrados:
        print(
            f"\n⚠️  {len(nao_encontrados)} municípios do mapeamento não existem "
            f"na tabela `municipio`:"
        )
        for n in nao_encontrados[:20]:
            print(f"     - {n}")
        if len(nao_encontrados) > 20:
            print(f"     ... e mais {len(nao_encontrados) - 20}")

    if ra_inexistente:
        print(
            f"\n⚠️  {len(ra_inexistente)} entradas apontam para RA não encontrada "
            f"em RA_METADATA — revise regioes_administrativas_sp_data.py:"
        )
        for e in ra_inexistente[:10]:
            print(f"     - {e}")

    # Municípios SP ainda sem RA (podem ser municípios ausentes no mapeamento)
    sem_ra = (
        session.execute(
            text("""
                SELECT m.nome
                  FROM municipio m
                  JOIN estado e ON m.estado_id = e.id
                 WHERE e.sigla = :uf
                   AND m.regiao_administrativa_id IS NULL
                 ORDER BY m.nome
            """),
            {"uf": SIGLA_UF},
        )
        .scalars()
        .all()
    )
    if sem_ra:
        print(
            f"\n⚠️  {len(sem_ra)} municípios de {SIGLA_UF} ainda sem RA "
            f"— adicione-os em regioes_administrativas_sp_data.py:"
        )
        for n in sem_ra[:20]:
            print(f"     - {n}")
        if len(sem_ra) > 20:
            print(f"     ... e mais {len(sem_ra) - 20}")

    print()
    return municipios_por_ra


# ---------------------------------------------------------------------------
# Etapa 3 — Calcular geometrias das RAs via ST_Union
# ---------------------------------------------------------------------------

def calcular_geometrias(session, municipios_por_ra: dict[int, list[int]]) -> None:
    """Atualiza regiao_administrativa.geom com a união das geometrias dos municípios."""
    print("[Load] Calculando geometria de cada RA (ST_Union dos municípios)...")

    for ra_id in municipios_por_ra:
        session.execute(
            text("""
                UPDATE regiao_administrativa
                   SET geom = sub.geom_uniao
                  FROM (
                    SELECT
                      ST_Multi(
                        ST_Union(m.geom)
                      )::geometry(MultiPolygon, 4326) AS geom_uniao
                    FROM municipio m
                   WHERE m.regiao_administrativa_id = :ra_id
                  ) sub
                 WHERE regiao_administrativa.id = :ra_id
            """),
            {"ra_id": ra_id},
        )

    session.commit()
    print("[Load] Geometrias calculadas.\n")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run() -> None:
    session = SessionLocal()
    try:
        estado = session.query(Estado).filter_by(sigla=SIGLA_UF).first()
        if estado is None:
            raise RuntimeError(
                f"Estado '{SIGLA_UF}' não encontrado. "
                "Execute `inserir_estado_municipio.py` antes desta pipeline."
            )

        mapa_ra          = inserir_regioes(session, estado.id)
        municipios_por_ra = vincular_municipios(session, mapa_ra)
        calcular_geometrias(session, municipios_por_ra)

        print("✅ Pipeline de Regiões Administrativas concluída!")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Execução direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()