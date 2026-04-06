#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de debug para rastrear o problema na busca de municípios.
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models.db_model import Municipio
from nlp_processor.pipeline.preprocessor import normalizar
from nlp_processor.pipeline.entity_extractor import extrair_entidades
from api.config.settings import settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def debug_municipio(municipio_input: str):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"\n{'='*60}")
    print(f"DEBUG: Buscando '{municipio_input}'")
    print(f"{'='*60}\n")

    # Passo 1: Normalizar input
    municipio_normalizado = normalizar(municipio_input)
    print(f"[1] Input: '{municipio_input}'")
    print(f"[1] Normalizado (Python): '{municipio_normalizado}'")
    print()

    # Passo 2: Extração de entidade
    entidades = extrair_entidades(municipio_input, [])
    print(f"[2] Entidade extraída: '{entidades.municipio}'")
    if entidades.municipio:
        municipio_extraido = normalizar(entidades.municipio)
        print(f"[2] Entidade normalizada: '{municipio_extraido}'")
    print()

    async with async_session() as session:
        # Passo 3: Buscar no banco
        print("[3] Municípios no banco (amostra):")
        stmt = select(Municipio.id, Municipio.nome, Municipio.nome_normalizado).limit(5)
        result = await session.execute(stmt)
        for row in result:
            print(f"    ID: {row[0]}, Nome: '{row[1]}', Normalizado: '{row[2]}'")
        print()

        # Passo 4: Buscar por nome_normalizado
        print(f"[4] Buscando por nome_normalizado = '{municipio_normalizado}'")
        stmt = select(Municipio.id, Municipio.nome, Municipio.nome_normalizado).where(
            Municipio.nome_normalizado == municipio_normalizado
        )
        result = await session.execute(stmt)
        rows = result.all()
        if rows:
            for row in rows:
                print(f"    ✓ ENCONTRADO! ID: {row[0]}, Nome: '{row[1]}', Normalizado: '{row[2]}'")
        else:
            print(f"    ✗ Não encontrado por nome_normalizado")
        print()

        # Passo 5: Busca por nome original normalizado em Python
        print(f"[5] Buscando por nome original (com normalização em Python):")
        stmt = select(Municipio.id, Municipio.nome).where(Municipio.nome.is_not(None))
        result = await session.execute(stmt)
        found = False
        for row_id, nome in result:
            nome_norm = normalizar(nome)
            if nome_norm == municipio_normalizado:
                print(f"    ✓ ENCONTRADO! ID: {row_id}, Nome: '{nome}' -> '{nome_norm}'")
                found = True
        if not found:
            print(f"    ✗ Não encontrado por nome original")
        print()

        # Passo 6: Listar todos com prefixo similar
        print(f"[6] Todos os municípios que começam com '{municipio_normalizado[:4]}':")
        stmt = select(Municipio.id, Municipio.nome, Municipio.nome_normalizado).where(
            Municipio.nome_normalizado.like(f"{municipio_normalizado[:4]}%")
        )
        result = await session.execute(stmt)
        rows = result.all()
        for row in rows[:10]:
            print(f"    ID: {row[0]}, Nome: '{row[1]}', Normalizado: '{row[2]}'")
        print()

    await engine.dispose()


if __name__ == "__main__":
    # Testar alguns municípios
    municipios_teste = [
        "são josé dos campos",
        "jacareí",
        "caçapava",
        "São Paulo",
    ]

    for municipio in municipios_teste:
        asyncio.run(debug_municipio(municipio))
        input("Pressione ENTER para continuar...")
