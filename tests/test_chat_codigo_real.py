# -*- coding: utf-8 -*-
"""
Teste end-to-end com código CAR REAL do banco
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from api.config.settings import settings
from models.db_model import ImovelRural, RelImovelQueimada
from nlp_processor.agent import run_agent


async def get_imovel_with_focos():
    """Encontra um imóvel com pelo menos 1 foco de queimada."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session_factory() as session:
        # Busca um imóvel que tem focos de queimada
        stmt = (
            select(
                ImovelRural.id,
                ImovelRural.codigo_car,
                func.count(RelImovelQueimada.id).label("total_focos")
            )
            .join(RelImovelQueimada, ImovelRural.id == RelImovelQueimada.imovel_rural_id)
            .group_by(ImovelRural.id, ImovelRural.codigo_car)
            .order_by(func.count(RelImovelQueimada.id).desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        
        await engine.dispose()
        
        if row:
            return row[1], row[2]  # codigo_car, total_focos
        return None, 0


async def test_com_codigo_real():
    """Testa o pipeline com um código CAR real."""
    
    # Encontra um código real
    codigo_car, total_focos = await get_imovel_with_focos()
    
    if not codigo_car:
        print("❌ Nenhum imóvel com focos de queimada encontrado no banco")
        return
    
    print(f"\n✅ Encontrado código CAR real: {codigo_car}")
    print(f"   Total de focos: {total_focos}\n")
    
    # Cria a pergunta
    pergunta = f"Na propriedade Rural {codigo_car} quantos focos de Incêndio houveram na região? (No ultimo ano/mes/semana)"
    
    print("=" * 80)
    print(f"TESTANDO PIPELINE NLP COM CÓDIGO CAR REAL")
    print("=" * 80)
    print(f"Pergunta: {pergunta}\n")
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session_factory() as session:
        try:
            resultado = await run_agent(
                session=session,
                pergunta=pergunta,
                historico=[],
            )
            
            print("\n" + "=" * 80)
            print("RESULTADO")
            print("=" * 80)
            print(f"\nStatus: {resultado.get('status')}")
            print(f"Intenção: {resultado.get('intencao')}")
            
            print(f"\n📝 Resposta:")
            print(resultado.get('texto_resposta'))
            
            features = resultado.get("features", [])
            print(f"\n📍 Features geoespaciais: {len(features)}")
            
            if features:
                print(f"\nPrimeiros focos encontrados:")
                for i, feat in enumerate(features[:5], 1):
                    props = feat.get("properties", {})
                    print(f"  {i}. Data: {props.get('data_ocorrencia')}, "
                          f"Intensidade: {props.get('intensidade')}")
            
            print("\n" + "=" * 80)
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_com_codigo_real())
