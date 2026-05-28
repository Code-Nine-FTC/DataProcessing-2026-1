import os
from pathlib import Path
from collections import defaultdict
from sqlalchemy import create_engine, text, func, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from api.config.settings import settings

from models.db_model import Estado, Municipio, RegiaoAdministrativa
from models.regioes_administrativas_sp_data import RA_METADATA, MUNICIPIO_TO_RA
from models.inserir_estado_municipio import normalizar


# ----------------------------------
# CONFIG
# ----------------------------------
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_raw_url = settings.DATABASE_URL
DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

SIGLA_UF = "SP"


# ----------------------------------
# LOAD
# ----------------------------------

def inserir_regioes(session, estado_id: int) -> dict:
    """Cria os 16 registros em regiao_administrativa (sem geometria ainda).
    Retorna dict {nome_normalizado_ra: ra_id}.
    """
    print("[Load] Inserindo Regiões Administrativas...")
    mapa_ra = {}

    for meta in RA_METADATA:
        nome = meta["nome"]
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
            session.flush()  # garante ra.id
            print(f"  + {meta['sigla']:8s} {nome}")
        else:
            print(f"  = {meta['sigla']:8s} {nome} (já existe, id={ra.id})")

        mapa_ra[nome_norm] = ra.id

    session.commit()
    return mapa_ra


def atualizar_municipios(session, mapa_ra: dict) -> dict:
    """Atualiza municipio.regiao_administrativa_id baseado em MUNICIPIO_TO_RA.
    Retorna dict {ra_id: [municipio_id, ...]} para uso no cálculo das geometrias.
    """
    print("[Load] Vinculando municípios às RAs...")

    municipios_por_ra = defaultdict(list)
    nao_encontrados = []
    sem_mapeamento_ra = []

    for nome_mun, nome_ra in MUNICIPIO_TO_RA.items():
        nome_mun_norm = normalizar(nome_mun)
        nome_ra_norm = normalizar(nome_ra)

        ra_id = mapa_ra.get(nome_ra_norm)
        if ra_id is None:
            sem_mapeamento_ra.append((nome_mun, nome_ra))
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

    total_vinculados = sum(len(v) for v in municipios_por_ra.values())
    print(f"[Load] Municípios vinculados: {total_vinculados}")

    if nao_encontrados:
        print(f"⚠️ {len(nao_encontrados)} municípios do mapeamento NÃO existem em `municipio`:")
        for nome in nao_encontrados[:20]:
            print(f"     - {nome}")
        if len(nao_encontrados) > 20:
            print(f"     ... e mais {len(nao_encontrados) - 20}")

    if sem_mapeamento_ra:
        print(f"⚠️ {len(sem_mapeamento_ra)} entradas referenciam RA inexistente em RA_METADATA")

    # Verifica municípios SP sem RA atribuída
    sem_ra = session.execute(
        text("""
            SELECT m.nome
            FROM municipio m
            JOIN estado e ON m.estado_id = e.id
            WHERE e.sigla = :uf AND m.regiao_administrativa_id IS NULL
            ORDER BY m.nome
        """),
        {"uf": SIGLA_UF},
    ).scalars().all()

    if sem_ra:
        print(f"⚠️ {len(sem_ra)} municípios de {SIGLA_UF} ainda sem RA (completar mapeamento em regioes_administrativas_sp_data.py)")

    return municipios_por_ra


def calcular_geometrias(session, municipios_por_ra: dict) -> None:
    """Computa a geometria de cada RA via ST_Union dos municípios vinculados."""
    print("[Load] Calculando geometria de cada RA (ST_Union)...")

    for ra_id, _ in municipios_por_ra.items():
        session.execute(
            text("""
                UPDATE regiao_administrativa
                   SET geom = sub.geom_uniao
                  FROM (
                      SELECT ST_Multi(ST_Union(m.geom))::geometry(MultiPolygon, 4326) AS geom_uniao
                        FROM municipio m
                       WHERE m.regiao_administrativa_id = :ra_id
                  ) sub
                 WHERE regiao_administrativa.id = :ra_id
            """),
            {"ra_id": ra_id},
        )

    session.commit()
    print("[Load] Geometrias calculadas.")


# ----------------------------------
# PIPELINE
# ----------------------------------

def run():
    session = SessionLocal()

    try:
        estado = session.query(Estado).filter_by(sigla=SIGLA_UF).first()
        if estado is None:
            raise RuntimeError(
                f"Estado {SIGLA_UF} não existe. Rode `inserir_estado_municipio.py` antes."
            )

        mapa_ra = inserir_regioes(session, estado.id)
        municipios_por_ra = atualizar_municipios(session, mapa_ra)
        calcular_geometrias(session, municipios_por_ra)

        print("✅ Pipeline de Regiões Administrativas finalizada!")

    finally:
        session.close()


# ----------------------------------
# MAIN
# ----------------------------------

if __name__ == "__main__":
    run()
