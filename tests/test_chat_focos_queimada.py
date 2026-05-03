# -*- coding: utf-8 -*-
"""
Teste end-to-end do pipeline NLP para consulta de focos de queimada.
Query: "Na propriedade Rural BR01231SP quantos focos de Incêndio houveram na região? (No ultimo ano/mes/semana)"
"""
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from api.config.settings import settings
from nlp_processor.agent import run_agent

logging.basicConfig(
    level=logging.DEBUG if settings.LOG_LEVEL == "DEBUG" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def test_chat_focos_queimada():
    """Testa a query de focos de queimada através do pipeline NLP."""
    
    # Configuração do banco
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession
    )
    
    pergunta = "Na propriedade Rural BR01231SP quantos focos de Incêndio houveram na região? (No ultimo ano/mes/semana)"
    historico = []
    
    logger.info("=" * 80)
    logger.info(f"Iniciando teste do chat NLP")
    logger.info(f"Pergunta: {pergunta}")
    logger.info("=" * 80)
    
    async with async_session_factory() as session:
        try:
            resultado = await run_agent(
                session=session,
                pergunta=pergunta,
                historico=historico,
            )
            
            print("\n" + "=" * 80)
            print("RESULTADO DO PIPELINE NLP")
            print("=" * 80)
            print(f"\nStatus: {resultado.get('status')}")
            print(f"Intenção: {resultado.get('intencao')}")
            print(f"\nResposta:\n{resultado.get('texto_resposta')}")
            
            if resultado.get("entidades"):
                print(f"\nEntidades extraídas:")
                for chave, valor in resultado.get("entidades", {}).items():
                    if valor is not None:
                        print(f"  {chave}: {valor}")
            
            features = resultado.get("features", [])
            print(f"\nTotal de features geoespaciais: {len(features)}")
            
            if features:
                print(f"\nPrimeiras 3 features (focos de queimada):")
                for i, feat in enumerate(features[:3], 1):
                    props = feat.get("properties", {})
                    print(f"  {i}. Data: {props.get('data_ocorrencia')}, "
                          f"Intensidade: {props.get('intensidade')}")
            
            fontes = resultado.get("fontes", [])
            if fontes:
                print(f"\nFontes de dados:")
                for font in fontes:
                    print(f"  - {font.get('nome')} ({font.get('orgao')})")
            
            print("\n" + "=" * 80)
            print("FIM DO TESTE")
            print("=" * 80)
            
            # Retorna resultado para análise
            return resultado
            
        except Exception as e:
            logger.exception("Erro durante execução do teste")
            raise
        finally:
            await engine.dispose()


async def test_entidade_extraction():
    """Testa especificamente a extração de entidades da query."""
    from nlp_processor.pipeline.entity_extractor import extrair_entidades
    
    pergunta = "Na propriedade Rural BR01231SP quantos focos de Incêndio houveram na região? (No ultimo ano/mes/semana)"
    
    logger.info("\n" + "=" * 80)
    logger.info("TESTE: Extração de Entidades")
    logger.info("=" * 80)
    logger.info(f"Pergunta: {pergunta}")
    
    municipios_norm = []  # Vazio para este teste - ser carregado em runtime
    entidades = extrair_entidades(pergunta, municipios_norm)
    
    print("\nEntidades extraídas:")
    print(f"  Código CAR: {entidades.codigo_car}")
    print(f"  Município: {entidades.municipio}")
    print(f"  Data Início: {entidades.data_inicio}")
    print(f"  Data Fim: {entidades.data_fim}")
    
    return entidades


async def test_intent_classification():
    """Testa especificamente a classificação de intenção."""
    from nlp_processor.pipeline.intent_classifier import get_classifier
    
    pergunta = "Na propriedade Rural BR01231SP quantos focos de Incêndio houveram na região? (No ultimo ano/mes/semana)"
    
    logger.info("\n" + "=" * 80)
    logger.info("TESTE: Classificação de Intenção")
    logger.info("=" * 80)
    logger.info(f"Pergunta: {pergunta}")
    
    classifier = get_classifier()
    intencao, confianca = classifier.predict(pergunta)
    
    print(f"\nIntenção detectada: {intencao}")
    print(f"Confiança: {confianca:.2%}")
    
    return intencao, confianca


if __name__ == "__main__":
    # Executa os testes
    print("\n🔍 TESTANDO PIPELINE NLP - FOCOS DE QUEIMADA\n")
    
    # Teste 1: Extração de Entidades
    entidades = asyncio.run(test_entidade_extraction())
    
    # Teste 2: Classificação de Intenção
    intencao, confianca = asyncio.run(test_intent_classification())
    
    # Teste 3: Pipeline Completo
    resultado = asyncio.run(test_chat_focos_queimada())
