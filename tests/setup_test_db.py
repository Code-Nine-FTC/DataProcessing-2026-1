#!/usr/bin/env python3
"""
Script de setup e verificação do banco de dados de teste PostGIS.
Usa as tabelas espaciais existentes do projeto.
"""

import asyncio
import os
import sys
import argparse
from sqlalchemy.ext.asyncio import create_async_engine
import sqlalchemy as sa


TEST_DB_CONFIG = {
    "user": "test",
    "password": "test",
    "host": "localhost",
    "port": 5432,
    "test_db": "test_db",
    "admin_db": "postgres"
}


async def create_database():
    """Cria o banco de dados de teste se não existir."""
    admin_url = f"postgresql+asyncpg://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['admin_db']}"
    
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_CONFIG['test_db']}'")
        )
        exists = result.scalar()
        
        if not exists:
            print(f"[SETUP] Criando banco de dados '{TEST_DB_CONFIG['test_db']}'...")
            await conn.execute(sa.text(f"CREATE DATABASE {TEST_DB_CONFIG['test_db']}"))
            print(f"[SETUP] Banco criado com sucesso!")
        else:
            print(f"[SETUP] Banco '{TEST_DB_CONFIG['test_db']}' já existe.")
    
    await engine.dispose()


async def setup_postgis():
    """Habilita a extensão PostGIS no banco de teste."""
    test_url = f"postgresql+asyncpg://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['test_db']}"
    
    engine = create_async_engine(test_url)
    
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text("SELECT extname FROM pg_extension WHERE extname LIKE 'postgis%'")
        )
        extensions = result.fetchall()
        
        if not extensions:
            print("[SETUP] Habilitando PostGIS...")
            await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
            print("[SETUP] PostGIS habilitado com sucesso!")
        else:
            print(f"[SETUP] PostGIS já habilitado: {[e[0] for e in extensions]}")
        
        result = await conn.execute(sa.text("SELECT postgis_version()"))
        version = result.scalar()
        print(f"[SETUP] PostGIS versão: {version}")
    
    await engine.dispose()


async def verify_test_tables():
    """Verifica as tabelas espaciais do projeto."""
    test_url = f"postgresql+asyncpg://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['test_db']}"
    
    engine = create_async_engine(test_url)
    
    async with engine.connect() as conn:
        print("[VERIFY] Verificando tabelas espaciais do projeto...")
        
        expected_tables = [
            'imovel_rural',
            'unidade_conservacao',
            'terra_indigena',
            'assentamento_rural',
            'queimada_evento',
            'desmatamento_alerta',
            'bacia_hidrografica',
            'territorio_quilombola'
        ]
        
        for table in expected_tables:
            try:
                result = await conn.execute(sa.text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                    )
                """))
                exists = result.scalar()
                if exists:
                    result = await conn.execute(sa.text(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' 
                        AND udt_name LIKE 'geometry%'
                    """))
                    geom_col = result.fetchone()
                    if geom_col:
                        print(f"  [OK] {table} ({geom_col[0]})")
                    else:
                        print(f"  [--] {table} (sem geometria)")
                else:
                    print(f"  [!!] {table} (nao existe)")
            except Exception as e:
                print(f"  [!] {table}: {e}")
        
        print("[VERIFY] Verificacao concluida!")
    
    await engine.dispose()


async def teardown():
    """Remove o banco de dados de teste."""
    admin_url = f"postgresql+asyncpg://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['admin_db']}"
    
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    async with engine.connect() as conn:
        await conn.execute(sa.text(f"""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = '{TEST_DB_CONFIG['test_db']}' AND pid <> pg_backend_pid()
        """))
        
        await conn.execute(sa.text(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['test_db']}"))
        print(f"[TEARDOWN] Banco '{TEST_DB_CONFIG['test_db']}' removido.")
    
    await engine.dispose()


async def verify_setup():
    """Verifica a configuração do banco de teste."""
    test_url = f"postgresql+asyncpg://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['test_db']}"
    
    engine = create_async_engine(test_url)
    
    async with engine.connect() as conn:
        print("\n[VERIFY] Verificando configuração...")
        
        result = await conn.execute(sa.text("SELECT postgis_version()"))
        print(f"  - PostGIS: {result.scalar()}")
        
        result = await conn.execute(sa.text("SELECT COUNT(*) FROM imovel_rural"))
        print(f"  - imovel_rural: {result.scalar()} registros")
        
        result = await conn.execute(sa.text("SELECT COUNT(*) FROM unidade_conservacao"))
        print(f"  - unidade_conservacao: {result.scalar()} registros")
        
        result = await conn.execute(sa.text("SELECT COUNT(*) FROM terra_indigena"))
        print(f"  - terra_indigena: {result.scalar()} registros")
    
    await engine.dispose()
    print("[VERIFY] Setup verificado com sucesso!\n")


async def main():
    parser = argparse.ArgumentParser(description="Setup do banco de testes PostGIS")
    parser.add_argument("--teardown", action="store_true", help="Remove o banco de teste")
    parser.add_argument("--verify", action="store_true", help="Verifica configuração atual")
    parser.add_argument("--full", action="store_true", help="Executa setup completo")
    args = parser.parse_args()
    
    if args.teardown:
        await teardown()
    elif args.verify:
        await verify_setup()
    elif args.full:
        print("\n=== Setup Completo do Banco de Testes ===\n")
        await create_database()
        await setup_postgis()
        await verify_test_tables()
        await verify_setup()
        print("=== Setup Concluído ===\n")
    else:
        print("\n=== Setup do Banco de Testes ===\n")
        await create_database()
        await setup_postgis()
        await verify_test_tables()
        print("\n=== Setup Concluído ===\n")
        print("Para verificar: python tests/setup_test_db.py --verify")
        print("Para remover:  python tests/setup_test_db.py --teardown")


if __name__ == "__main__":
    asyncio.run(main())