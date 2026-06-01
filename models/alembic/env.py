from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncConnection
from api.config.settings import settings
from models.db_model import Base
import asyncio
from sqlalchemy import text
from models.inserir_estado_municipio import run
from models.inserir_regiao_administrativa import run as run_ra

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in ("spatial_ref_sys",):
        return False
    if type_ == "index" and (name.startswith("idx_") or name.endswith("_geom_idx")):
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: AsyncConnection) -> None:
    """Roda dentro de connection.run_sync() — contexto síncrono."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        print("-" * 50)
        print("🔧 Verificando/Instalando extensões (PostGIS, Vector, Unaccent)...")
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        print("✅ Extensões prontas!")
        print("-" * 50)
        print("🚀 Executando migrações de tabelas...")
        context.run_migrations()
        print("✅ Migrações concluídas!")
        print("-" * 50)
    # ETLs fora do bloco de transação do Alembic — usam engine própria (psycopg2)


async def run_async_migrations() -> None:
    try:
        connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()

    except ConnectionRefusedError as e:
        print(f"❌ Conexão recusada: {e}")
        print("Verifique se o banco está rodando e as credenciais estão corretas.")
        raise
    except Exception as e:
        print(f"❌ Erro durante as migrações: {e}")
        raise

    # ETLs rodam APÓS a conexão assíncrona ser fechada — evita conflito de drivers
    print("📥 Inserindo estado e municípios...")
    run()
    print("✅ Estado e municípios inseridos!")
    print("-" * 50)
    print("📥 Inserindo Regiões Administrativas...")
    run_ra()
    print("✅ Regiões Administrativas inseridas!")
    print("-" * 50)


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()