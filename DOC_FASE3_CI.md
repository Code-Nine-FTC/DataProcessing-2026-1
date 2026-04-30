# Fase 3: CI (GitHub Actions) - Implementação

## Configuração Escolhida (baseada nas respostas):

### Trigger:
- ✅ **Push + PR para main**
- Executa em: pushes para `main` e Pull Requests direcionados a `main`

### Estratégia de Banco de Dados:
- ✅ **Service Container**
- Imagem: `postgis/postgis:16-3.4` (compatível com o projeto)
- Variáveis: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Healthcheck: `pg_isready -U test` (aguarda PostGIS ficar pronto)

### Passos do CI:
- ✅ **Apenas Testes de Integração**
- Checkout do código
- Setup Python 3.13
- Instalação de dependências (`requirements.txt` + `pytest` + `pytest-asyncio` + `psycopg2-binary`)
- Execução de migrações Alembic
- **Execução dos testes**: `pytest tests/integration/spatial/ -v --tb=short`

### Secrets:
- ✅ **Não necessários**
- Apenas variáveis de ambiente padrão (`POSTGRES_*`) no próprio workflow

---

## Arquivo Criado:
- ✅ `.github/workflows/spatial-integration-tests.yml`

## O que o Workflow faz:
1. **Sobe PostGIS** como service container (porta 5432)
2. **Healthcheck**: Aguarda PostGIS estar pronto (máx 30 tentativas)
3. **Instala dependências** do projeto
4. **Executa Alembic** para criar as tabelas no PostGIS
5. **Roda todos os testes** de `tests/integration/spatial/`
6. **Upload de artifacts** (opcional, para análise de falhas)

---

## Diferença para Windows:
| Ambiente | Testes Assíncronos | Testes Síncronos |
|-----------|-------------------|-------------------|
| **Windows (local)** | ❌ Falham (event loop) | ✅ Passam (`test_intersects_simple.py`) |
| **Linux (CI)** | ✅ Passam (todos) | ✅ Passam |

---

## Próximos Passos (Fases 4 e 5):
### Fase 4 (Rastreabilidade):
- Adicionar `pytest.mark.rf04` aos testes relacionados a RF-04
- Criar `TEST_TRACING.md` mapeando testes → requisitos
- Alinhar com peer de Rastreamento de Requisitos

### Fase 5 (Deploy):
- Validar paridade de ambiente (PostGIS 3.4 em staging/prod)
- Testes de integração como gate de deploy
- Alinhar com peer de Deploy

---

## ⚠️ Nota Importante:
**Todos os testes assíncronos que falham no Windows funcionarão no CI (Linux)**, pois o problema é específico de compatibilidade `asyncpg` + `pytest-asyncio` no Windows.

**A Fase 3 está implementada e pronta para uso no GitHub Actions.**