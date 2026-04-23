import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check_srid():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/visiona')
    try:
        async with engine.connect() as conn:
            print("\n--- Verificando SRIDs no Banco de Dados ---")
            for table in ['terra_indigena', 'territorio_quilombola', 'assentamento_rural', 'unidade_conservacao']:
                try:
                    result = await conn.execute(text(f"SELECT ST_SRID(geom) as srid, COUNT(*) as total FROM {table} GROUP BY ST_SRID(geom)"))
                    rows = result.fetchall()
                    if rows:
                        print(f"Tabela '{table}':")
                        for r in rows:
                            print(f"  -> SRID encontrado: {r.srid} (Total de registros: {r.total})")
                    else:
                        print(f"Tabela '{table}': Vazia")
                except Exception as e:
                    pass
    except Exception as e:
        print(f"Erro ao conectar ao BD: {e}")

if __name__ == '__main__':
    asyncio.run(check_srid())
