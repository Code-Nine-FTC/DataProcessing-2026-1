# DataProcessing-2026-1

API para processamento de dados geoespaciais.

## 🛠️ Tecnologias Principais

- **Python 3.12**
- **FastAPI** (Framework Web)
- **SQLAlchemy 2.0** (ORM Assíncrono)
- **Alembic** (Migrações de Banco de Dados)
- **PostgreSQL + PostGIS** (Dados Geoespaciais)
- **PGVector** (Busca Vetorial para IA)
- **Pydantic Settings** (Gestão de Configurações)

## 🚀 Como Executar o Projeto

### 1. Preparar o Ambiente
Certifique-se de ter o Python e o Docker instalados.

```bash
# Criar ambiente virtual
python3 -m venv .venv

# Ativar ambiente virtual
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configuração de Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/nome_do_banco
```

### 3. Subir o Banco de Dados
Utilize o Docker Compose para iniciar os serviços necessários (PostgreSQL com extensões):
```bash
# Para Iniciar o Docker Compose
docker compose up -d

# Para remover os serviços Docker
docker compose down -v
```

### 4. Migrações do Banco de Dados
O projeto utiliza o Alembic para gerenciar as tabelas e extensões (PostGIS/Vector).

```bash
#Inicie o Alembic
alembic init alembic

#Substitua o arquivo alembic/env.py com o seguinte conteúdo:
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncConnection
from api.config.settings import settings
from models.db_model import Base
import asyncio
from sqlalchemy import text

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
        print("🔧 Verificando/Instalando extensões (PostGIS & Vector)...")
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        print("🚀 Executando migrações de tabelas...")
        context.run_migrations()
        print("✅ Tudo pronto!")

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

```bash
# Substituição do Arquivo alembic/script.py.mako com o seguinte conteúdo:
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 
import pgvector
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
```

```bash
# Gerar a migração inicial (se necessário)
alembic revision --autogenerate -m "initial_migration"

# Aplicar as migrações ao banco de dados
alembic upgrade head
```

## 📂 Estrutura de Pastas

- `api/`: Configurações globais e rotas.
- `models/`: Definições das tabelas SQLAlchemy (Modelos).
- `data-ingestion/`: Scripts para carga de dados.
- `nlp-processor/`: Scripts para processamento de linguagem natural.

---
*Desenvolvido para fins acadêmicos - FATEC 2026-1*