# Plano de Implementação: Testes de Integração para Queries Espaciais
*Alinhado a Martin Fowler (DevOps: colaboração, self-testing build, paridade de ambiente, test pyramid)*

---

## Pré-condições (já atendidas pelo repositório)
- `docker-compose.yml` com serviço de DB PostgreSQL
- Migrações Alembic configuradas (`models/alembic/`)
- `pytest.ini` existente
- Dependências espaciais: `GeoAlchemy2`, `shapely`, `psycopg2-binary` em `requirements.txt`

---

## Fase 1: Estrutura Base (Prova de Conceito) – *Prioridade definida por você*
**Esforço**: 2-3 dias | **Independente de outros peers** | **Princípio Fowler: Self-Testing Build**

### Passos
1. **Criar estrutura de diretórios**
   ```
   tests/
   ├── integration/
   │   └── spatial/
   │       ├── conftest.py       # Fixtures centralizadas
   │       ├── seed_data.py      # Dados de teste via migração + seed
   │       └── test_intersects_db_model.py  # Primeiro teste (prova de conceito)
   ```

2. **Implementar `conftest.py` (fixtures de ambiente)**
   - Fixture de DB PostGIS: Reutiliza o `docker-compose.yml` existente ou usa imagem `postgis/postgis:16-3.4` (matching produção)
   - Fixture de migração: Executa `alembic upgrade head` no DB de teste via `asyncio` + `asyncpg`
   - Fixture de sessão: `AsyncSession` do SQLAlchemy (padrão do repositório)
   - Fixture de seed: Insere geometrias mínimas válidas (GeoJSONs de pontos/polígonos conhecidos para validação previsível)

3. **Implementar `seed_data.py`**
   - Insere 3-5 registros em tabelas chave (`imovel_rural`, `desmatamento`, `municipio`) com geometrias conhecidas para testar `ST_Intersects`, `ST_Buffer`, etc.

4. **Primeiro teste funcional**
   - Testa `db_model.get_imoveis_intersecting_geometry` (linha 192 de `models/db_model.py`)
   - Valida se uma geometria de teste intersecta os registros seedados corretamente

5. **Execução local**
   ```bash
   docker-compose up -d db && pytest tests/integration/spatial/test_intersects_db_model.py -v
   ```

### Entregável
- Estrutura base funcional com 1 teste passando
- Fixtures reutilizáveis para todas as queries espaciais

---

## Fase 2: Cobertura Completa de Queries Espaciais
**Esforço**: 5-7 dias | **Independente, com validação do PO** | **Princípio Fowler: Test Pyramid (camada de integração)**

### Escopo (todas as queries espaciais, conforme sua escolha)
| Arquivo Alvo | Funções Espaciais a Testar |
|--------------|----------------------------|
| `models/db_model.py` | `ST_Intersects` (linha 201) |
| `api/services/index.py` | `ST_Buffer` (linha 464), `ST_Distance` (linha 422), `ST_DWithin` (linha 426), `ST_Intersects` (linha 472) |
| `nlp_processor/tools.py` | `ST_Intersects` (linhas 351, 374, 449, 544, 637, 730) |
| `data-ingestion/sources/relacoes_espaciais.py` | `ST_Area`, `ST_Intersection` (linha 90) |
| `api/router/analytics.py` | Endpoints RF-04 completos |

### Passos
1. Criar um arquivo de teste por função espacial (evita acoplamento):
   - `test_intersects.py`
   - `test_buffer.py`
   - `test_distance.py`
   - `test_area.py`
2. Para cada query:
   - Inserir dados seed específicos para a função
   - Executar a função real (sem mocks de PostGIS)
   - Validar resultado espacial (ex: "buffer de 5km deve conter 2 imóveis")

### Entregável
- 90%+ de cobertura de todas as queries espaciais do repositório
- Zero mocks de funções PostGIS (princípio de integração real)

---

## Fase 3: Integração ao CI (GitHub Actions)
**Esforço**: 2-3 dias | **Depende do peer de CI** | **Princípio Fowler: Continuous Integration**

### Passos
1. Criar `.github/workflows/integration-tests.yml` (estrutura para GitHub Actions, sua escolha):
   ```yaml
   name: Spatial Integration Tests
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       services:
         postgis:
           image: postgis/postgis:16-3.4
           env:
             POSTGRES_DB: test_db
             POSTGRES_USER: test_user
             POSTGRES_PASSWORD: test_pass
           ports: ["5432:5432"]
       steps:
         - uses: actions/checkout@v4
         - run: pip install -r requirements.txt
         - run: alembic upgrade head
         - run: pytest tests/integration/spatial/ -v --tb=short
   ```

2. **Alinhar com peer de CI**:
   - Timeout para testes espaciais (máx 5min)
   - Armazenamento de logs de teste como artefato
   - Gatilho: rodar em todos os PRs para `main`

### Entregável
- Testes rodando automaticamente no GitHub Actions
- Build falha se testes de integração falharem

---

## Fase 4: Rastreabilidade e Alinhamento de Time
**Esforço**: 2 dias | **Depende de peers de Rastreamento e Testes Unitários** | **Princípio Fowler: Build Transparency**

### Passos
1. **Marcadores de requisitos (pytest)**:
   ```python
   @pytest.mark.rf04  # Vincula ao requisito [RF-04] de analytics
   @pytest.mark.spatial
   def test_desmatamento_buffer_imoveis():
       ...
   ```

2. **Alinhar com peer de Rastreamento de Requisitos**:
   - Mapear marcadores de teste ao sistema de gestão deles (Jira/Azure DevOps)
   - Criar `TEST_TRACING.md` com relação teste → requisito de negócio

3. **Alinhar com peer de Testes Unitários**:
   - Confirmar que testes unitários mockam funções espaciais (evitar sobreposição)
   - Integração usa banco real, unitário usa mocks (respeito ao Test Pyramid)

### Entregável
- Rastreabilidade completa de teste → requisito de negócio
- Zero sobreposição com testes unitários

---

## Fase 5: Alinhamento com Deploy e Paridade de Ambiente
**Esforço**: 1-2 dias | **Depende de peer de Deploy** | **Princípio Fowler: Environment Parity**

### Passos
1. Compartilhar configuração de PostGIS do `conftest.py` com peer de Deploy:
   - Versão do PostGIS (3.4)
   - Extensões habilitadas (`CREATE EXTENSION IF NOT EXISTS postgis`)
   - SRID padrão (4326, conforme migrações)

2. Validar que testes de integração passam em ambiente de staging (pós-deploy)

3. Definir testes de integração como validação pós-deploy (rollback se falhar)

### Entregável
- Paridade total entre teste, staging e produção
- Testes de integração como gate de deploy

---

## Dependências Resumidas
| O que você pode fazer sozinho | O que depende de peers |
|--------------------------------|------------------------|
| Fases 1 e 2 (estrutura + cobertura) | Fase 3 (CI) |
| Escrever testes locais | Fase 4 (Rastreamento) |
| Definir seed data | Fase 5 (Deploy) |

*Princípio Fowler: Não espere peers para começar. Entregue a Fase 1 em 2 dias e use como moeda de troca para alinhar o restante do pipeline.*

---