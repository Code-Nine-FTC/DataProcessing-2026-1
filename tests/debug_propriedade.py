# -*- coding: utf-8 -*-
"""
Debug: Verificar dados da propriedade BR01231SP no banco
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from api.config.settings import settings
from models.db_model import ImovelRural, RelImovelQueimada, QueimadaEvento


async def debug_propriedade():
    """Verifica dados da propriedade BR01231SP."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session_factory() as session:
        # 1. Verifica se o código CAR existe
        print("\n" + "=" * 80)
        print("1️⃣  BUSCANDO PROPRIEDADE COM CÓDIGO CAR: BR01231SP")
        print("=" * 80)
        
        stmt = select(ImovelRural).where(ImovelRural.codigo_car == "BR01231SP")
        result = await session.execute(stmt)
        imovel = result.scalars().first()
        
        if imovel:
            print(f"✅ Propriedade encontrada!")
            print(f"   ID: {imovel.id}")
            print(f"   Código CAR: {imovel.codigo_car}")
            print(f"   Municipio ID: {imovel.municipio_id}")
            
            # 2. Verifica focos de queimada para essa propriedade
            print("\n" + "=" * 80)
            print("2️⃣  BUSCANDO FOCOS DE QUEIMADA")
            print("=" * 80)
            
            stmt_rel = (
                select(func.count(RelImovelQueimada.id))
                .where(RelImovelQueimada.imovel_rural_id == imovel.id)
            )
            result_rel = await session.execute(stmt_rel)
            total_rel = result_rel.scalar()
            
            print(f"Total de relacionamentos (rel_imovel_queimada): {total_rel}")
            
            if total_rel > 0:
                # Busca os focos associados
                stmt_focos = (
                    select(QueimadaEvento)
                    .join(RelImovelQueimada, QueimadaEvento.id == RelImovelQueimada.queimada_evento_id)
                    .where(RelImovelQueimada.imovel_rural_id == imovel.id)
                    .order_by(QueimadaEvento.data_ocorrencia.desc())
                )
                result_focos = await session.execute(stmt_focos)
                focos = result_focos.scalars().all()
                
                print(f"\nDetalhes dos focos:")
                for i, foco in enumerate(focos[:10], 1):
                    print(f"  {i}. Data: {foco.data_ocorrencia}, "
                          f"Intensidade: {foco.intensidade}")
        else:
            print(f"❌ Propriedade COM COM CÓDIGO CAR 'BR01231SP' NÃO ENCONTRADA")
            
            # Lista alguns códigos CAR para referência
            print("\n" + "=" * 80)
            print("📋 LISTANDO ALGUNS CÓDIGOS CAR DISPONÍVEIS")
            print("=" * 80)
            
            stmt_lista = (
                select(ImovelRural.codigo_car, func.count(ImovelRural.id))
                .group_by(ImovelRural.codigo_car)
                .limit(10)
            )
            result_lista = await session.execute(stmt_lista)
            rows = result_lista.all()
            
            print(f"Exemplos de códigos CAR no banco:")
            for codigo, count in rows:
                print(f"  {codigo} ({count} imóvel(is))")
            
            # Tenta buscar por código similar
            print("\n" + "=" * 80)
            print("🔍 BUSCANDO POR 'BR01231' (parcial)")
            print("=" * 80)
            
            stmt_partial = (
                select(ImovelRural.codigo_car)
                .where(ImovelRural.codigo_car.like("BR01231%"))
                .limit(5)
            )
            result_partial = await session.execute(stmt_partial)
            codigos = result_partial.scalars().all()
            
            if codigos:
                print(f"Códigos CAR com prefixo 'BR01231':")
                for cod in codigos:
                    print(f"  {cod}")
            else:
                print("Nenhum código CAR com prefixo 'BR01231' encontrado")
        
        # 3. Estatísticas gerais
        print("\n" + "=" * 80)
        print("📊 ESTATÍSTICAS GERAIS DO BANCO")
        print("=" * 80)
        
        stmt_total_imovel = select(func.count(ImovelRural.id))
        total_imovel = (await session.execute(stmt_total_imovel)).scalar()
        
        stmt_total_rel = select(func.count(RelImovelQueimada.id))
        total_rel_geral = (await session.execute(stmt_total_rel)).scalar()
        
        stmt_total_queimada = select(func.count(QueimadaEvento.id))
        total_queimada = (await session.execute(stmt_total_queimada)).scalar()
        
        print(f"Total de imóveis rurais: {total_imovel}")
        print(f"Total de focos de queimada: {total_queimada}")
        print(f"Total de relacionamentos imovel-queimada: {total_rel_geral}")
        
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(debug_propriedade())
