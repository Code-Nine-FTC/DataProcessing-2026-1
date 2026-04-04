# 🏛️ Arquitetura Técnica

## 5 Camadas

### 1. **Presentation** (main.py)
CLI para coordenar operações. Interface simples para o usuário.

### 2. **Orchestration** (etl/orchestrator.py)
`PipelineOrchestrator` coordena:
- Registro de pipelines
- Execução sequencial
- Coleta de resultados

### 3. **Pipeline** (etl/pipeline.py)
`BasePipeline` template que coordena:
```
Extract → Ensure FonteDado → Create Dataset → Transform → Load
```

### 4. **ETL Layers** (etl/)

**Extractors**: Busca dados
- `WFSExtractor`: WFS com paginação
- `CSVExtractor`: CSV local

**Transformers**: Normaliza dados
- `GeometricTransformer`: Com geometria

**Loaders**: Insere dados
- `GeometricLoader`: PostGIS com geometria

### 5. **Foundation**

**Infrastructure** (infrastructure/):
- `WFSClient`: Reutilizável para qualquer WFS
- `Repositories`: Acesso a dados

**Core** (core/):
- `config.py`: Configuração centralizada
- `exceptions.py`: 7 exceções custom
- `models.py`: DTOs, interfaces

**Domain** (domain/):
- `entities.py`: 11 entidades puras

---

## Padrões de Design

| Padrão | Uso |
|--------|-----|
| Factory | `create_pipeline()` em cada source |
| Template Method | `BasePipeline.run()` |
| Strategy | Extractors/Transformers/Loaders |
| Repository | Acesso a dados |
| Dependency Injection | Via `__init__()` |

---

## Adicionar Nova Fonte (Template)

```python
# 1. Constantes
SOURCE = DataSource(name="...", url="...")
_FIELD = ("name1", "name2", "name3")

# 2. Extrator
class MyExtractor(WFSExtractor):
    def extract(self) -> ExtractedData: pass

# 3. Transformador
class MyTransformer(GeometricTransformer):
    def transform_feature(self, f) -> TransformedRecord: pass

# 4. Carregador
class MyLoader(GeometricLoader):
    def get_insert_query(self) -> str: pass

# 5. Pipeline
class MyPipeline(BasePipeline):
    def _get_dataset_name(self) -> str: ...
    def _get_dataset_description(self) -> str: ...

# 6. Factory
def create_pipeline(engine, wfs_client):
    return MyPipeline(...)
```

---

## Fluxo de Dados

```
Input
  ↓
Orchestrator.run_all()
  ↓
Para cada pipeline:
  ├─ EXTRACT (WFS/CSV) → ExtractedData
  ├─ ENSURE FonteDado → fonte_id
  ├─ CREATE Dataset → dataset_id
  ├─ TRANSFORM → list[TransformedRecord]
  ├─ LOAD → LoadResult
  └─ Transação ACID (tudo ou nada)

Resultado: Banco carregado com dados normalizados
```

---

## Exceções

```
PipelineException (base)
  ├─ ExtractionException
  ├─ TransformationException
  ├─ LoadException
  ├─ ValidationException
  ├─ ConfigException
  └─ DataSourceException
```

---

## ACID & Idempotência

**Transações**: `with engine.begin()` garante rollback em erro

**Idempotência**: Dataset verifica duplicatas
```sql
SELECT id FROM dataset
WHERE fonte_dado_id = ? AND nome = ?
```
Se existe: **skip** (não duplica)

---

## PostGIS Queries

Exemplo de relacionamento espacial:
```sql
INSERT INTO rel_imovel_uc
SELECT uuid, ir.id, uc.id,
  ST_Area(ST_Intersection(ir.geom, uc.geom)) / 10000,
  CASE WHEN ST_Contains(uc.geom, ir.geom) THEN 'dentro' END
FROM imovel_rural ir
JOIN unidade_conservacao uc ON ST_Intersects(ir.geom, uc.geom)
```

---

## Configuração

Via variáveis de ambiente:
```bash
DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
WFS_TIMEOUT=120
WFS_BATCH_SIZE=500
DEBUG=false
LOG_LEVEL=INFO
```

---

## Performance

- **Bulk Insert**: 1000+ registros/batch
- **WFS Pagination**: Chunks de 500
- **Connection Pool**: SQLAlchemy gerencia
- **índices Recomendados**: `geom`, `id_origem`

---

## Testabilidade

Cada camada mockável:
```python
# Mock Extractor
mock_gdf = gpd.GeoDataFrame(...)
data = extractor.extract()

# Mock Transformer
records = transformer.transform(data)

# Mock Loader
result = loader.load(records, dataset_id)
```

---

**Última atualização**: 2026-04-02
