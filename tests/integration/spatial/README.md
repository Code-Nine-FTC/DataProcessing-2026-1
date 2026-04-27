# Documentação de Testes de Integração Espaciais

## Visão Geral

Este documento descreve a infraestrutura de testes de integração para queries espaciais do projeto, utilizando PostgreSQL/PostGIS real para garantir que todas as operações geoespaciais funcionam corretamente.

## Por Que Testes de Integração?

### Diferença entre Testes Unitários e Integração

| Aspecto | Unitário | Integração |
|---------|----------|-----------|
| Dependências | Mockadas | Reais |
| Banco de dados | Não usa | PostGIS real |
| Validação | Lógica isolada | Sistema completo |
| Performance | Rápido | Moderado |
| Confiabilidade | Média | Alta |

### Por Que PostGIS Real?

1. **Funções espaciais completas**: ST_Intersects, ST_Buffer, ST_DWithin, etc.
2. **Índices espaciais**: GiST/SP-GiST funcionam corretamente
3. **SRID/CRS**: Validação de sistemas de coordenadas reais
4. **Comportamento real**: Erros e exceções do banco real

## Quick Start

### Executando Localmente

```bash
# 1. Setup do banco de teste
python tests/setup_test_db.py --full

# 2. Executar todos os testes
pytest tests/integration/spatial/ -v

# 3. Executar apenas testes de erro
pytest tests/integration/spatial/test_error_scenarios.py -v
```

### Usando Script de Automação

```bash
python tests/run_tests.py --verbose        # Saída detalhada
python tests/run_tests.py --coverage     # Com coverage
python tests/run_tests.py --errors-only  # Apenas cenários de erro
```

## Estrutura dos Testes

### Arquivos

```
tests/
├── setup_test_db.py              # Setup automático do banco
├── run_tests.py                 # Script de automação
├── check_postgis.py           # Verifica PostGIS
└── integration/spatial/
    ├── conftest.py            # Fixtures pytest
    ├── test_intersection_queries.py
    ├── test_buffer_queries.py
    ├── test_proximity_queries.py
    ├── test_contains_function.py
    ├── test_performance.py
    ├── test_analytics_queries.py
    ├── test_geometry_validity.py
    ├── test_spatial_relationships.py
    ├── test_error_scenarios.py      # Testes de erro
    └── README.md
```

### Fixture `conftest.py`

```python
@pytest.fixture()
async def engine():
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost:5432/test_db")
    yield engine
    await engine.dispose()

@pytest.fixture()
async def db_session(engine):
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def sample_point():
    return WKTElement("POINT(-46.633 -23.583)", srid=4326)
```

## Cenários de Erro Testados

### TestGeometryErrors

```python
async def test_invalid_geometry_wkt():
    """WKT inválido deve lançar exceção."""
    with pytest.raises((ProgrammingError, InternalError)):
        await db_session.execute(text("SELECT ST_GeomFromText('INVALID', 4326)"))

async def test_null_geometry_handling():
    """Geometria nula retorna NULL."""
    result = await db_session.execute(text("""
        SELECT ST_Intersects(NULL, ST_GeomFromText('POINT(0 0)', 4326))
    """))
    assert result.scalar() is None
```

### TestSRIDErrors

- SRIDs mistos (4326 vs 4674)
- SRID nulo (0)
- Transformação com SRID inválido

### TestTopologyErrors

- Polígono auto-intersectado
- Polígono degenerado
- Geometria válida

### TestPerformanceErrors

- Timeout de query
- Dataset grande
- Índice espacial

## CI/CD - GitHub Actions

### workflow.yml

```yaml
name: Testes de Integração Espaciais

on: [push, pull_request]

jobs:
  test-spatial:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.6
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pytest pytest-asyncio sqlalchemy geoalchemy2 asyncpg
      - name: Setup test database
        run: python tests/setup_test_db.py --full
      - name: Run tests
        run: pytest tests/integration/spatial/ -v
```

## Variáveis de Ambiente

```bash
# .env
POSTGRES_USER=test
POSTGRES_PASSWORD=test
POSTGRES_DB=test_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## Exemplos de Queries Testadas

### Interseção

```sql
SELECT ST_Intersects(
    ST_SetSRID(ST_GeomFromText(:geom), 4326),
    ST_GeomFromText('POLYGON((-46.634 -23.584, ...))', 4326)
) AS intersects;
```

### Buffer

```sql
SELECT ST_Area(ST_Buffer(geometria, 1000)) AS buffer_area
FROM imovel_rural
WHERE ST_DWithin(geometria, :point, 5000);
```

### Proximidade

```sql
SELECT ST_Distance(i.geometria, q.geometria) AS distance
FROM imovel_rural i
JOIN queimada_evento q ON ST_DWithin(i.geometria, q.geometria, 10000);
```

## Justificativa Técnicas

### Por Que pytest?

1. **Padrão Python**: Maior adoção em projetos Python
2. **Fixtures**: Gerenciamento de estado de teste
3. **Async support**: pytest-asyncio para SQLAlchemy async
4. **Marker support**: Categorização de testes
5. **CI/CD integration**: Facilidade com GitHub Actions

### Por Que Banco Real?

1. **PostGIS não é mockável**: Funções espaciais reais necessárias
2. **Índices espaciais**: GiST/SP-GiST testados corretamente
3. **SRID validation**: CRS real (4326, 4674) testado

### Por Que Isolamento?

1. **Dados limpos**: Sem contaminar dados de produção
2. **Reprodutibilidade**: Ambiente consistente
3. **Teste paralelo**: Possível sem conflitos

## Resultados Atuais

```
Testes espaciais: 22 passed
Testes de erro:   21 passed
```

## Comandos Úteis

```bash
# Setup completo
python tests/setup_test_db.py --full

# Verificar configuração
python tests/setup_test_db.py --verify

# Remover banco de teste
python tests/setup_test_db.py --teardown

# Executar com coverage
pytest tests/integration/spatial/ --cov=. --cov-report=html

# Execução paralela
pytest tests/integration/spatial/ -n auto

# Relatório JUnit (para CI)
pytest tests/integration/spatial/ --junit-xml=test-results/junit.xml
```

## Referências

- [PostGIS Documentation](https://postgis.net/docs/)
- [pytest Documentation](https://docs.pytest.org/)
- [GeoAlchemy2 Documentation](https://geoalchemy-2.readthedocs.io/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/)