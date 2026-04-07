from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncConnection
from api.config.settings import settings
from models.db_model import Base
import asyncio
from sqlalchemy import text
from models.inserir_estado_municipio import run
config = context.config

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in ("spatial_ref_sys"):
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

async def run_async_migrations() -> None:
    try:
        connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()

    except ConnectionRefusedError as e:
        print(f"Database connection refused: {e}")
        print("Please check if the database server is running and the connection details are correct.")
        raise
    except Exception as e:
        print(f"An error occurred while running migrations: {e}")
        raise

def do_run_migrations(connection: AsyncConnection) -> None:

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        print("-"*50)
        print("🔧 Verificando/Instalando extensões (PostGIS & Vector)...")
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("-"*50)
        print("🚀 Executando migrações de tabelas...")
        context.run_migrations()
        print("✅ Tudo pronto!")
        print("-"*50)
    print("📥 Inserindo dados de estado e municípios...")
    run()
    print("✅ Dados inseridos com sucesso!")
    print("-"*50)
def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()