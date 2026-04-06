#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para preencher o campo nome_normalizado para todos os municípios.
"""
import asyncio
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models.db_model import Municipio
from nlp_processor.pipeline.preprocessor import normalizar
from api.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_municipio_normalizado():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Buscar todos os municípios com nome não-nulo
        stmt = select(Municipio.id, Municipio.nome).where(
            Municipio.nome.is_not(None)
        )
        result = await session.execute(stmt)
        rows = result.all()

        logger.info(f"Encontrados {len(rows)} municípios para processar")

        updates_count = 0
        for municipio_id, nome in rows:
            nome_normalizado = normalizar(nome)

            # Atualizar o campo
            update_stmt = (
                update(Municipio)
                .where(Municipio.id == municipio_id)
                .values(nome_normalizado=nome_normalizado)
            )
            await session.execute(update_stmt)
            updates_count += 1

            if updates_count % 100 == 0:
                logger.info(f"Processados {updates_count}/{len(rows)} municípios")

        await session.commit()
        logger.info(f"Preenchimento concluído! {updates_count} municípios atualizados")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill_municipio_normalizado())
