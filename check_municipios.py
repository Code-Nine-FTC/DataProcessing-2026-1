#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')

async def check_db():
    engine = create_async_engine(db_url, echo=False)
    async with AsyncSession(engine) as session:
        # 1. Tipo do campo
        result = await session.execute(text('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name='municipio' AND column_name='nome'
        '''))
        print('=== 1. TIPO DO CAMPO nome ===')
        for row in result:
            print(f'{row[0]}: {row[1]}')
        
        # 2. Verificar duplicatas e variações
        result = await session.execute(text('''
            SELECT nome, COUNT(*) as qtd 
            FROM municipio 
            GROUP BY nome 
            HAVING COUNT(*) > 1
        '''))
        print('\n=== 2. DUPLICATAS EXATAS ===')
        rows = result.all()
        if rows:
            for row in rows:
                print(f'{row[0]}: {row[1]}x')
        else:
            print('Nenhuma duplicata exata encontrada')
        
        # 3. Verificar variações de case/acentuação (primeiros 10)
        result = await session.execute(text('''
            SELECT DISTINCT nome FROM municipio ORDER BY nome LIMIT 15
        '''))
        print('\n=== 3. AMOSTRA DE NOMES (15 primeiros) ===')
        for row in result:
            print(f'  {row[0]}')
        
        # 4. Contar total de municípios
        result = await session.execute(text('''
            SELECT COUNT(*) FROM municipio
        '''))
        print(f'\n=== 4. TOTAL DE MUNICÍPIOS ===')
        print(result.scalar())
        
    await engine.dispose()

asyncio.run(check_db())
