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
POSTGRES_USER = user
POSTGRES_PASSWORD = password
POSTGRES_DB = nome_do_banco_de_dados
POSTGRES_HOST = localhost
POSTGRES_PORT = 5432
```

### 3. Subir o Banco de Dados
Utilize o Docker Compose para iniciar os serviços necessários (PostgreSQL com extensões):
```bash
# Para Iniciar o Docker Compose
docker compose up -d

# Para remover os serviços Docker
docker compose down -v
```

4. **Configurar o VSCode**:
    - Crie uma pasta `.vscode` na raiz do projeto.
    - Dentro da pasta `.vscode`, crie o arquivo `settings.json` e adicione:
    ```json
        {
        "terminal.integrated.env.windows": {
            "PYTHONPYCACHEPREFIX": "${workspaceFolder}/.pycache_global"
        },
        "terminal.integrated.env.linux": {
            "PYTHONPYCACHEPREFIX": "${workspaceFolder}/.pycache_global"
        },
        "terminal.integrated.env.osx": {
            "PYTHONPYCACHEPREFIX": "${workspaceFolder}/.pycache_global"
        },
        "python.analysis.extraPaths": [
            "${workspaceFolder}"
        ],
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.terminal.activateEnvInSelectedTerminal": true
    }
    ```
    - Dentro da pasta `.vscode`, crie o arquivo `launch.json` e adicione:
    ```json
    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "FastAPI Debug",
                "type": "debugpy",
                "request": "launch",
                "module": "uvicorn",
                "args": [
                    "api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5050",
                ],
                "env": {
                    "PYTHONPYCACHEPREFIX": "${workspaceFolder}/.pycache_global"
                },
                "console": "integratedTerminal"
            }
        ]
    }
    ```

### 5. Migrações do Banco de Dados
O projeto utiliza o Alembic para gerenciar as tabelas e extensões (PostGIS/Vector).

```bash
# Gerar a migração inicial (se necessário)
alembic revision --autogenerate -m "initial_migration"

# Aplicar as migrações ao banco de dados
alembic upgrade head
```

### 6. Para a inserção de dados
```bash 
# Inserir dados
python data-ingestion/main.py
```

### 7. Treinar o Pipeline NLP
Antes de usar o chat/agente NLP, é necessário treinar o classificador de intenções:

```bash
# Treinar o modelo de intenção (gera joblib no nlp_processor/models/)
python -m nlp_processor.training.train
```

8. **Rodar a aplicação**:
    - Para rodar a aplicação:
    ```bash
    python -m api/main.py
    ```
    ou
    ```bash
    uvicorn api.main:app --reload --port 5000
    ```
    - Para rodar com o modo debugger, basta apertar `F5` no VSCode.

## 📂 Estrutura de Pastas

- `api/`: Configurações globais e rotas.
- `models/`: Definições das tabelas SQLAlchemy (Modelos).
- `data-ingestion/`: Scripts para carga de dados.
- `nlp-processor/`: Scripts para processamento de linguagem natural.

---
*Desenvolvido para fins acadêmicos - FATEC 2026-1*