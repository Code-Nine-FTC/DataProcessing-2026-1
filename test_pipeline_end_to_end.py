#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste end-to-end da busca de municípios pelo chat.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from api.config.settings import settings
from nlp_processor.agent import run_agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_chat():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    perguntas = [
        "queimadas em são josé dos campos",
        "focos de incêndio em jacareí",
        "caçapava",
        "incêndios em São Paulo",
    ]

    async with async_session() as session:
        for pergunta in perguntas:
            print(f"\n{'='*70}")
            print(f"PERGUNTA: {pergunta}")
            print(f"{'='*70}")

            try:
                texto, features, fontes, status = await run_agent(
                    session=session,
                    pergunta=pergunta,
                    historico=[],
                )

                print(f"\nSTATUS: {status}")
                print(f"RESPOSTA: {texto[:200]}...")
                print(f"FEATURES: {len(features)} resultado(s)")
                print(f"FONTES: {len(fontes)} source(s)")

                if features:
                    for i, feature in enumerate(features[:3]):
                        print(f"  [{i+1}] {feature.get('properties', {})}")
                else:
                    print("  (nenhum resultado)")

            except Exception as e:
                logger.exception(f"Erro ao processar: {pergunta}")
                print(f"ERRO: {e}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_chat())
