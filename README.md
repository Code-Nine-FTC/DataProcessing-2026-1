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

---

### 1. Preparar o Ambiente
Certifique-se de ter o Python e o Docker instalados. Além disso, é necessário criar as pastas obrigatórias para o Airflow e garantir as permissões de escrita:

```bash
# Criar ambiente virtual
python3 -m venv .venv
# Ativar ambiente virtual
source .venv/bin/activate
# Instalar dependências
pip install -r requirements.txt

# Criar pastas obrigatórias para volumes do Airflow
mkdir -p ./logs ./dags ./plugins 

# Definir permissões de escrita para o Docker (usuário 50000)
sudo chown -R 50000:0 ./logs ./dags ./plugins ./api/config
sudo chmod -R 775 ./logs ./dags ./plugins ./api/config
```

### 2. Configuração de Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
# Banco de Dados
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=airflow_db
POSTGRES_HOST=database
POSTGRES_PORT=5432

# Airflow
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://user:password@database/airflow_db
AIRFLOW__CORE__FERNET_KEY=  # Gere com: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
AIRFLOW__WEBSERVER__SECRET_KEY=  # Gere com: openssl rand -hex 32
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW_UID=50000

# Credenciais da Web UI
AIRFLOW_WWW_USER_USERNAME=airflow
AIRFLOW_WWW_USER_PASSWORD=airflow
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
