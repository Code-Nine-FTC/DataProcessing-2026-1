# Plano de Reconstrução do NLP — DataProcessing / Visiona
### Versão 2.0 — Arquitetura Profissional com Clean Architecture

> **Documento de especificação e execução.**
> Para executar: entregue este arquivo como comando — "execute o PLANO_RECONSTRUCAO_NLP.md".
>
> **Premissas inegociáveis:**
> - 100% local. Zero dependência de API externa paga.
> - O **transformer (mpnet)** é o cérebro do entendimento — não a LLM.
> - A **LLM local** é usada **somente como fallback** de baixa confiança.
> - Todo o processo NLP (pré-processamento → entendimento → resposta) é construído pela equipe,
>   justificável academicamente e explicável numa banca.
> - Clean Architecture + Clean Code + documentação impecável.

---

## 1. Por que reconstruir?

### O problema central do código atual
O sistema atual possui **três "cérebros" concorrentes** que se atropelam:

1. **`intent_classifier.py`** — TF-IDF + LogReg decide a intenção...
2. **`agent.py`** (`_resolver_intencao_final`) — ...mas 7 regras hardcoded **sobrescrevem** essa decisão...
3. **`entity_extractor.py`** — ...e regex de 536 linhas **também decide** pedaços da intenção.

Consequência: adicionar uma capacidade nova exige editar **6 arquivos diferentes**, sem garantia
de coerência. Isso não é escalável.

### Por que o transformer, não a LLM, é a escolha certa aqui
| Critério | Transformer (mpnet) | LLM como cérebro |
|---|---|---|
| Acadêmico | ✅ Processo NLP feito pela equipe | ❌ Caixa preta terceirizada |
| Performance | ✅ Sub-segundo, local, sem GPU cara | ❌ Centenas de ms por chamada |
| Explicabilidade | ✅ Similaridade de cosseno é auditável | ❌ Não justificável numa banca |
| Custo | ✅ Zero (modelo já carregado pro RAG) | ❌ Infra de serving, memória |
| Já usado no projeto | ✅ mpnet já carregado para RAG | ❌ Modelo extra |

O `paraphrase-multilingual-mpnet-base-v2` **já está no projeto, já está em memória** e foi
escolhido exatamente por entender português. Reutilizá-lo para entendimento de intenção é a
decisão tecnicamente correta — não carregar um segundo modelo para fazer o mesmo trabalho.

**A LLM fica para fallback** — quando a confiança do sistema é baixa demais para responder
deterministicamente. Isso é honesto com o usuário e profissional.

---

## 2. Princípios de Engenharia

### Clean Architecture
O sistema é dividido em **camadas com dependência de dentro para fora**. Camadas internas
nunca conhecem camadas externas:

```
┌──────────────────────────────────────┐
│  INTERFACE (index.py)                │  ← ponto de entrada público
├──────────────────────────────────────┤
│  APPLICATION (pipeline/ + engine/)   │  ← orquestra os casos de uso
├──────────────────────────────────────┤
│  DOMAIN (contracts.py + domains/)    │  ← regras e contratos — sem dependência externa
├──────────────────────────────────────┤
│  INFRASTRUCTURE (llm/ + db/ + emb/)  │  ← detalhes técnicos (banco, LLM, embedder)
└──────────────────────────────────────┘
```

### Clean Code — regras aplicadas
- **Uma responsabilidade por arquivo.** Nenhum arquivo faz mais de uma coisa.
- **Nomes revelam intenção.** `parse_query`, `ground_entities`, `execute_specs`, `compose_response`.
- **Funções pequenas.** Máximo de ~30 linhas por função.
- **Sem comentário do óbvio.** Comentário só para o "porquê" não-óbvio.
- **Sem magic numbers/strings.** Tudo em constantes ou enums.
- **Contratos tipados (Pydantic).** Nenhum `dict` solto entre estágios.
- **Dependency injection.** Nenhuma dependência instanciada dentro de função de negócio.

---

## 3. Arquitetura: Pipeline Linear de 5 Estágios

```
   PERGUNTA (texto livre)
         │
         ▼
┌────────────────────┐
│  1. PRÉ-PROCESSAR  │  higiene + correção ortográfica + normalização
│  text_hygiene.py   │        ↓
│                    │  TextoProcessado{ original, normalizado, corrigido }
└────────────────────┘
         │
         ▼
┌────────────────────┐
│  2. ENTENDER       │  transformer (mpnet) → similaridade semântica
│  semantic_router.py│        ↓
│                    │  PlanoConsulta{ specs: list[QuerySpec], confiança }
└────────────────────┘
         │
         ├── confiança < threshold? ──────────────────────────────────┐
         │                                                             ▼
         ▼                                                  ┌──────────────────┐
┌────────────────────┐                                      │  FALLBACK LLM    │
│  3. EXTRAIR        │  entidades determinísticas            │  llm_fallback.py │
│  entity_extractor  │  (Aho-Corasick + regex + banco)       │  (Ollama local)  │
│  .py               │        ↓                             └──────────────────┘
│                    │  QuerySpec validado com IDs                     │
└────────────────────┘                                                 │
         │                                                             │
         ▼                                                             │
┌────────────────────┐                                                 │
│  4. BUSCAR         │  motor declarativo (ORM + PostGIS)              │
│  query_engine.py   │  asyncio.gather (paralelo por spec)             │
│                    │        ↓                                        │
│                    │  list[ToolResult]                               │
└────────────────────┘                                                 │
         │                                                             │
         ▼                                                             │
┌────────────────────┐                                                 │
│  5. RESPONDER      │  renderização determinística sobre ToolResult   │
│  responder.py      │        ↓                                        │
│                    │  RespostaNLP{ texto, geojson, fontes, bbox }    │
└────────────────────┘                                                 │
         │                                                             │
         └───────────────────────────────── (merge) ──────────────────┘
         ▼
   RESPOSTA FINAL  →  persiste no banco (consulta_usuario + resposta_sistema)
```

**Regra de ouro:** a informação só anda para frente. Nenhum estágio olha para o anterior.

---

## 4. Contratos Tipados — `domain/contracts.py`

> Este é o coração da arquitetura. Os contratos são **imutáveis e compartilhados por todos os
> estágios**. Alterar um contrato é a única forma de adicionar capacidade ao sistema.

```python
# domain/contracts.py

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enumerações de domínio ──────────────────────────────────────────────────

class Dominio(str, Enum):
    """O "o quê" da consulta. Adicionar domínio = 1 linha aqui + 1 DomainSpec."""
    QUEIMADA             = "queimada"
    DESMATAMENTO         = "desmatamento"
    UNIDADE_CONSERVACAO  = "unidade_conservacao"
    TERRA_INDIGENA       = "terra_indigena"
    QUILOMBOLA           = "quilombola"
    ASSENTAMENTO         = "assentamento"
    IMOVEL_RURAL         = "imovel_rural"
    CAMADA_ESTADUAL      = "camada_estadual"
    DOCUMENTO            = "documento"   # RAG


class Operacao(str, Enum):
    """O "como" da consulta. Cada combinação Dominio×Operacao é suportada automaticamente."""
    LISTAR   = "listar"    # busca padrão com features para o mapa
    RANKEAR  = "rankear"   # ex-buscar_maiores_quantidades
    SOBREPOR = "sobrepor"  # ex-buscar_sobreposicao_areas
    PASSIVOS = "passivos"  # passivos de um imóvel específico


# ── Blocos do QuerySpec ─────────────────────────────────────────────────────

class LocalConsulta(BaseModel):
    municipio_nome: Optional[str] = None
    municipio_id: Optional[int] = None      # preenchido pelo grounding
    regiao_administrativa_nome: Optional[str] = None
    regiao_administrativa_id: Optional[int] = None
    codigo_car: Optional[str] = None


class PeriodoConsulta(BaseModel):
    data_inicio: Optional[str] = None   # ISO yyyy-mm-dd
    data_fim: Optional[str] = None


class FiltrosConsulta(BaseModel):
    bioma: Optional[str] = None
    categoria_uc: Optional[str] = None
    esfera_uc: Optional[str] = None
    grupo_snuc: Optional[str] = None
    fase_ti: Optional[str] = None
    tipo_alerta: Optional[str] = None
    sensor: Optional[str] = None
    limite: int = 50
    tema_ranking: Optional[str] = None   # para Operacao.RANKEAR
    tema_sobreposicao_a: Optional[str] = None
    tema_sobreposicao_b: Optional[str] = None


class ContextoEspacial(BaseModel):
    """Filtro de área protegida: 'queimadas DENTRO DE terras indígenas'."""
    dentro_de: Optional[Dominio] = None


# ── Contratos entre estágios ────────────────────────────────────────────────

class TextoProcessado(BaseModel):
    """Saída do estágio 1 (PRÉ-PROCESSAR)."""
    original: str
    normalizado: str        # lowercase, sem acentos
    corrigido: str          # pós spell-check
    tokens: list[str]
    embedding: Optional[list[float]] = None   # gerado pelo router


class QuerySpec(BaseModel):
    """Uma consulta atômica. Pergunta composta = list[QuerySpec]."""
    dominio: Dominio
    operacao: Operacao = Operacao.LISTAR
    onde: LocalConsulta = Field(default_factory=LocalConsulta)
    periodo: Optional[PeriodoConsulta] = None
    filtros: FiltrosConsulta = Field(default_factory=FiltrosConsulta)
    contexto_espacial: Optional[ContextoEspacial] = None


class PlanoConsulta(BaseModel):
    """Saída do estágio 2 (ENTENDER). Lista suporta perguntas compostas nativamente."""
    specs: list[QuerySpec]
    confianca: float          # 0.0–1.0; abaixo do threshold → fallback LLM
    fora_escopo: bool = False


class Fonte(BaseModel):
    nome: str
    orgao: Optional[str] = None
    url: Optional[str] = None


class ToolResult(BaseModel):
    """Saída do estágio 4 (BUSCAR). Só dados — zero prosa."""
    dominio: Dominio
    operacao: Operacao
    total: int
    features: list[dict] = Field(default_factory=list)
    resumo: dict = Field(default_factory=dict)
    fontes: list[Fonte] = Field(default_factory=list)
    spec: QuerySpec
    bbox: Optional[list[float]] = None
    sql_executado: Optional[str] = None


class RespostaNLP(BaseModel):
    """Saída final do pipeline (estágio 5)."""
    texto: str
    features: list[dict]
    bbox: Optional[list[float]]
    fontes: list[Fonte]
    status: str   # "sucesso" | "sem_resultado" | "fora_escopo" | "fallback" | "erro"
    confianca: float
    sql_executado: Optional[str] = None
    tempo_ms: int = 0
```

---

## 5. Detalhe de cada estágio

### Estágio 1 — PRÉ-PROCESSAR (`pipeline/text_hygiene.py`)

**Responsabilidade única:** receber texto bruto e devolver `TextoProcessado`.

**Por que pré-processamento importa mesmo com transformer:**
O transformer entende semântica, mas texto com erros ortográficos graves ("keiimada",
"dezmatamento") pode produzir embeddings menos precisos porque o tokenizador do modelo não
reconhece a palavra e a fragmenta em subwords aleatórios. A correção ortográfica **antes** da
vetorização melhora a qualidade do embedding.

**O que faz (em ordem):**
1. **Higiene** — `strip`, colapsar espaços múltiplos, remover caracteres de controle.
2. **Correção ortográfica** — `pyspellchecker` com dicionário PT-BR. Corrige erros de digitação
   comuns ("keiimada" → "queimada", "dezmatamento" → "desmatamento").
3. **Normalização** — lowercase + `unidecode` (remove acentos) para a cópia `normalizado`.
   A cópia `corrigido` mantém acentos (vai para o transformer).
4. **Tokenização** — split + remoção de stopwords PT-BR (para uso interno no extrator de entidades,
   não para o transformer — que recebe o texto completo).

**O que NÃO faz:** lematização nem stemming na cópia que vai ao transformer. O mpnet foi treinado
com texto natural; lematizar destrói morfologia que ele usa.

**Biblioteca:** `pyspellchecker` (dicionário PT-BR embutido, sem dependência de serviço externo).

---

### Estágio 2 — ENTENDER (`pipeline/semantic_router.py`)

**Responsabilidade única:** transformar `TextoProcessado` em `PlanoConsulta`.

**Como funciona — Semantic Tool Routing:**
Cada domínio+operação do sistema possui um conjunto de **frases de exemplo** (os 289 exemplos
atuais do `train_data.py` viram exatamente isso). No boot, todos os exemplos são embeddados com
o **mpnet** e armazenados em memória como uma matriz.

Para cada pergunta:
1. Embeda a pergunta (`corrigido`) com o mesmo mpnet.
2. Calcula **similaridade de cosseno** entre a pergunta e todos os exemplos.
3. Retorna o(s) domínio(s) com maior score acima do threshold.
4. Perguntas compostas → top-k domínios distintos acima do threshold = múltiplos `QuerySpec`.

```
embedding(pergunta) · embedding(exemplo_i)
────────────────────────────────────────── = score_i   (para cada exemplo)
‖pergunta‖ × ‖exemplo_i‖

top domínios por score agregado → list[QuerySpec]
```

**Por que isso é superior ao TF-IDF atual:**
- "fogo em Campinas" → cai próximo de "queimadas em Campinas" no espaço vetorial, mesmo sem
  ter "queimada" no texto. O TF-IDF não faz isso.
- Multi-intenção sai de graça (top-k), sem heurística de split em "e".
- Adicionar exemplo = uma linha no `examples.py`. Sem retreinar. Sub-segundo.

**Confiança:** média dos scores do top match. Abaixo de `CONFIDENCE_THRESHOLD` (configurável,
default 0.55) → `PlanoConsulta.confianca < threshold` → fallback LLM.

**O embedding é gerado UMA vez** e reutilizado para o RAG (evita duplo processamento).

---

### Estágio 3 — EXTRAIR (`pipeline/entity_extractor.py`)

**Responsabilidade única:** preencher os slots de `QuerySpec` (onde, quando, filtros).

**Mudanças em relação ao atual:**
- Extração de **município**: Aho-Corasick sobre os 645 municípios do banco (não uma lista
  hardcoded de ~90). Match em O(n) no tamanho do texto, não O(n_municípios).
- **Datas, CAR, bioma, categoria_uc, etc.**: regex determinístico mantido e reorganizado.
- Períodos relativos ("último mês", "este ano") normalizados para ISO aqui.
- Nenhuma lógica de intenção aqui — o extrator só preenche slots, nunca decide o domínio.

---

### Fallback — LLM LOCAL (`pipeline/llm_fallback.py`)

**Acionado somente quando** `confianca < CONFIDENCE_THRESHOLD`.

**O que a LLM recebe:**
- A pergunta original.
- O histórico da conversa.
- Uma descrição concisa do escopo do sistema (o que ele sabe e não sabe responder).

**O que a LLM devolve:** uma `RespostaNLP` com `status="fallback"` — resposta em linguagem
natural explicando que o sistema não compreendeu ou está fora do escopo.

**A LLM nunca acessa o banco, nunca monta query, nunca inventa dados.**
Ela só redige uma mensagem amigável para o usuário.

**Runtime:** Ollama local. Modelo recomendado: `qwen2.5-3B-Instruct` (pequeno, rápido, só
para texto, sem necessidade de structured output).

---

### Estágio 4 — BUSCAR (`engine/query_engine.py` + `engine/domain_registry.py`)

**Responsabilidade única:** transformar `list[QuerySpec]` em `list[ToolResult]`.

**Motor declarativo — por que 1 motor > 40 funções:**

As 40 funções atuais de `tools.py` seguem o mesmo padrão:
*domínio X + filtros Y → select() ORM + PostGIS → features + contagem + fontes.*

Isso é uma **declaração**, não código. Vira uma `DomainSpec` por domínio:

```python
# engine/domain_registry.py
REGISTRY: dict[Dominio, DomainSpec] = {
    Dominio.QUEIMADA: DomainSpec(
        model=QueimadaEvento,
        geom_col="geom",
        filtros_map={"bioma": QueimadaEvento.bioma,
                     "periodo": QueimadaEvento.data_ocorrencia},
        rel_imovel=RelImovelQueimada,
        fonte_join=(Dataset, FonteDado),
    ),
    Dominio.DESMATAMENTO: DomainSpec(
        model=DesmatamentoAlerta,
        geom_col="geom",
        filtros_map={"tipo_alerta": DesmatamentoAlerta.tipo_alerta,
                     "periodo": DesmatamentoAlerta.data_ocorrencia},
        rel_imovel=RelImovelDesmatamento,
        fonte_join=(Dataset, FonteDado),
    ),
    # ... uma entrada por domínio
}
```

O motor lê a `DomainSpec` e monta o `select()` ORM genericamente.
Adicionar domínio = adicionar uma entrada no `REGISTRY`. O SQL é o mesmo de hoje — só a
organização muda. **Performance idêntica, zero duplicação.**

As specs rodam em **paralelo** com `asyncio.gather` — pergunta composta não é mais lenta que
simples (as queries são independentes).

---

### Estágio 5 — RESPONDER (`pipeline/responder.py`)

**Responsabilidade única:** transformar `list[ToolResult]` em `RespostaNLP`.

**Como funciona — renderização orientada a dados:**
Em vez de um `_TEMPLATES` dict de strings hardcoded por ferramenta (hoje são ~20 templates),
o responder usa um sistema de **renderização orientada ao `ToolResult`**:

```
ToolResult{ dominio, operacao, total, resumo, fontes }
    → seleção de renderer por (dominio, operacao)
    → renderer acessa os dados do resultado (nunca o texto original)
    → produz texto estruturado em PT-BR
```

Adicionar domínio = escrever um renderer de ~10 linhas. Sem copiar template.

O **geojson + bbox + fontes** saem diretamente dos `ToolResult` sem passar por renderização
(dados puros, sem interpretação). Só o `texto` passa pelo renderer.

---

## 6. Estrutura de Pastas (Clean Architecture)

```
nlp_processor/
│
├── PLANO_RECONSTRUCAO_NLP.md          # este documento
│
├── domain/                            # CAMADA DE DOMÍNIO (sem dependências externas)
│   ├── __init__.py
│   ├── contracts.py                   # QuerySpec, ToolResult, RespostaNLP, etc. (§4)
│   ├── enums.py                       # Dominio, Operacao (separado para import circular)
│   └── exceptions.py                  # NLPError, OutOfScopeError, LowConfidenceError
│
├── pipeline/                          # CAMADA DE APLICAÇÃO — estágios do pipeline
│   ├── __init__.py
│   ├── text_hygiene.py                # Estágio 1: pré-processamento + spell-check
│   ├── semantic_router.py             # Estágio 2: entendimento via transformer
│   ├── entity_extractor.py            # Estágio 3: extração de slots (Aho-Corasick + regex)
│   ├── responder.py                   # Estágio 5: renderização de ToolResult → texto
│   └── llm_fallback.py                # Fallback: LLM local (Ollama) para baixa confiança
│
├── engine/                            # CAMADA DE APLICAÇÃO — execução de queries
│   ├── __init__.py
│   ├── domain_spec.py                 # DomainSpec (declaração de domínio)
│   ├── domain_registry.py             # REGISTRY: dict[Dominio, DomainSpec]
│   ├── query_engine.py                # motor genérico ORM+PostGIS → ToolResult
│   └── geo_helpers.py                 # ST_AsGeoJSON, ST_Simplify, bbox helpers
│
├── infrastructure/                    # CAMADA DE INFRAESTRUTURA (detalhes técnicos)
│   ├── __init__.py
│   ├── embedder.py                    # sentence-transformers mpnet (mantido do atual)
│   ├── gazetteer.py                   # Aho-Corasick sobre municípios/RAs do banco
│   ├── llm_client.py                  # cliente Ollama (OpenAI-compatible)
│   └── rag.py                         # busca vetorial pgvector (mantida do atual)
│
├── examples/                          # exemplos de treinamento do router semântico
│   ├── __init__.py
│   └── intent_examples.py             # dict[Dominio, list[str]] — os 289 exemplos migrados
│
├── orchestrator.py                    # maestro: chama os 5 estágios em ordem
├── index.py                           # interface pública (NLPProcessor) — não muda a API
│
└── tests/
    ├── __init__.py
    ├── conftest.py                    # fixtures (sessão, exemplos, mocks)
    ├── unit/
    │   ├── test_text_hygiene.py       # testa correção ortográfica, normalização
    │   ├── test_semantic_router.py    # testa routing por similaridade
    │   ├── test_entity_extractor.py   # testa município, CAR, datas
    │   └── test_responder.py          # testa renderização por domínio
    ├── integration/
    │   ├── test_query_engine.py       # testa motor ORM contra banco de teste
    │   └── test_pipeline.py           # testa estágios 3→4→5 integrados
    └── e2e/
        └── golden_set.py              # 289 perguntas → RespostaNLP esperada (ex-train_data)
```

---

## 7. O Maestro (`orchestrator.py`)

O arquivo mais importante para legibilidade. O sistema inteiro cabe em 15 linhas:

```python
# orchestrator.py

async def run(
    session: AsyncSession,
    pergunta: str,
    historico: list[dict],
    municipio_contexto: str | None = None,
) -> RespostaNLP:
    inicio = perf_counter()

    # 1. Pré-processar
    texto = text_hygiene.processar(pergunta)

    # 2. Entender
    plano = await semantic_router.entender(texto, historico)

    # Fallback se confiança baixa
    if plano.fora_escopo or plano.confianca < settings.CONFIDENCE_THRESHOLD:
        return await llm_fallback.responder(pergunta, historico)

    # 3. Extrair entidades e validar contra o banco
    specs = await entity_extractor.extrair_e_validar(session, plano, municipio_contexto)

    # 4. Buscar (paralelo por spec)
    resultados = await query_engine.executar(session, specs)

    # 5. Responder
    resposta = responder.compor(resultados, historico)

    return resposta.model_copy(update={"tempo_ms": _ms(inicio)})
```

Qualquer desenvolvedor lê isso e entende o sistema em 30 segundos.

---

## 8. Vocabulário de Domínio — `domain/vocabulary.py`

> Padrão diretamente inspirado no `representation-nlp-codenine`.
> Este arquivo é **o único lugar** onde se define o que o sistema entende e como isso vira query.
> Adicionar capacidade = adicionar uma `Categoria` ou um `GrupoSemantico` aqui. Nada mais.

### Por que sementes e não exemplos

| | Exemplos (abordagem anterior) | Sementes (este padrão) |
|---|---|---|
| Quantidade | Dezenas por classe | **3–5 por categoria** |
| "fogo" cobre "queimada"? | Só se estiver listado | ✅ O transformer generaliza automaticamente |
| Adicionar categoria | Retreinar modelo | Adicionar 3–5 sementes + reiniciar indexação |
| Manutenção | Arquivos `.joblib` versionados | Código Python puro, versionado com git |

O transformer embeda as sementes como **âncoras no espaço vetorial**. Qualquer frase que caia
próxima de uma âncora é reconhecida — sem ter sido vista antes. Isso é o que torna o sistema
escalável sem crescimento de dados.

### Estrutura do vocabulário

```python
# domain/vocabulary.py

@dataclass(frozen=True)
class Categoria:
    rotulo: str            # identificador interno
    query_spec: dict       # o que isso vira no QuerySpec (substitui DISPATCH)
    sementes: tuple[str, ...]  # âncoras semânticas (3–5 são suficientes)


@dataclass(frozen=True)
class GrupoSemantico:
    """Um grupo é uma dimensão ortogonal classificada independentemente.
    Grupos diferentes podem acender ao mesmo tempo na mesma pergunta."""
    nome: str
    categorias: tuple[Categoria, ...]
    limiar: float          # score mínimo de cosseno para ativar


# ── Grupos do domínio ambiental ─────────────────────────────────────────────

QUEIMADA = GrupoSemantico("queimada", limiar=0.72, categorias=(
    Categoria("listar", {"dominio": "queimada", "operacao": "listar"}, (
        "focos de queimada",
        "incêndio florestal",
        "fogo registrado",
        "foco de calor",
        "queimada detectada",
    )),
    Categoria("rankear", {"dominio": "queimada", "operacao": "rankear"}, (
        "municípios com mais queimadas",
        "ranking de focos de incêndio",
        "quais cidades tiveram mais fogo",
    )),
))

DESMATAMENTO = GrupoSemantico("desmatamento", limiar=0.72, categorias=(
    Categoria("listar", {"dominio": "desmatamento", "operacao": "listar"}, (
        "alertas de desmatamento",
        "supressão de vegetação",
        "corte raso de floresta",
        "alerta PRODES",
        "alerta DETER",
    )),
    Categoria("rankear", {"dominio": "desmatamento", "operacao": "rankear"}, (
        "municípios com mais desmatamento",
        "ranking de supressão vegetal",
    )),
))

TERRA_INDIGENA = GrupoSemantico("terra_indigena", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "terra_indigena", "operacao": "listar"}, (
        "terras indígenas",
        "área de demarcação indígena",
        "reserva indígena",
        "território indígena demarcado",
    )),
))

UNIDADE_CONSERVACAO = GrupoSemantico("unidade_conservacao", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "unidade_conservacao", "operacao": "listar"}, (
        "unidades de conservação",
        "parque nacional estadual",
        "área de proteção ambiental",
        "reserva extrativista",
    )),
))

QUILOMBOLA = GrupoSemantico("quilombola", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "quilombola", "operacao": "listar"}, (
        "territórios quilombolas",
        "comunidades quilombolas",
        "áreas quilombolas",
    )),
))

IMOVEL_RURAL = GrupoSemantico("imovel_rural", limiar=0.75, categorias=(
    Categoria("listar", {"dominio": "imovel_rural", "operacao": "listar"}, (
        "imóveis rurais",
        "fazenda cadastrada no CAR",
        "propriedade rural",
        "código CAR",
    )),
    Categoria("passivos", {"dominio": "imovel_rural", "operacao": "passivos"}, (
        "passivos ambientais do imóvel",
        "sobreposição da propriedade com áreas protegidas",
        "infrações do imóvel rural",
    )),
))

# Contexto espacial é um grupo ORTOGONAL — ativa junto com o grupo principal
# "queimadas DENTRO DE terras indígenas" → QUEIMADA + CONTEXTO_ESPACIAL ambos ativam
CONTEXTO_ESPACIAL = GrupoSemantico("contexto_espacial", limiar=0.80, categorias=(
    Categoria("terra_indigena", {"contexto_espacial": {"dentro_de": "terra_indigena"}}, (
        "dentro de terras indígenas",
        "nas áreas indígenas",
        "que intersectam territórios indígenas",
    )),
    Categoria("unidade_conservacao", {"contexto_espacial": {"dentro_de": "unidade_conservacao"}}, (
        "dentro de unidades de conservação",
        "em parques e reservas",
        "nas UCs",
    )),
    Categoria("quilombola", {"contexto_espacial": {"dentro_de": "quilombola"}}, (
        "em territórios quilombolas",
        "dentro de áreas quilombolas",
    )),
))

OPERACAO_ESPECIAL = GrupoSemantico("operacao_especial", limiar=0.82, categorias=(
    Categoria("sobrepor", {"operacao": "sobrepor"}, (
        "sobreposição entre áreas",
        "intersecção de camadas territoriais",
        "cruzamento entre UC e TI",
    )),
    Categoria("rankear_geral", {"operacao": "rankear", "dominio": None}, (
        "quais municípios têm mais",
        "ranking geral de municípios",
        "maior concentração de dados ambientais",
    )),
))

GRUPOS: tuple[GrupoSemantico, ...] = (
    QUEIMADA, DESMATAMENTO, TERRA_INDIGENA, UNIDADE_CONSERVACAO,
    QUILOMBOLA, IMOVEL_RURAL, CONTEXTO_ESPACIAL, OPERACAO_ESPECIAL,
)
```

### Como o motor usa o vocabulário

O `MotorSemantico` (igual ao `representation-nlp-codenine`) **classifica cada grupo
independentemente**. Para "queimadas dentro de terras indígenas":

```
score(QUEIMADA.listar)            = 0.91 ✅ > limiar 0.72
score(CONTEXTO_ESPACIAL.ti)       = 0.88 ✅ > limiar 0.80
score(DESMATAMENTO.listar)        = 0.41 ❌ < limiar
score(TERRA_INDIGENA.listar)      = 0.52 ❌ < limiar (a TI é contexto, não domínio aqui)

→ QuerySpec{ dominio=QUEIMADA, operacao=LISTAR, contexto_espacial={dentro_de=TERRA_INDIGENA} }
```

Nenhuma regra. Nenhum override. O vocabulário fez o trabalho.

---

## 9. Tecnologias e justificativas

| Tecnologia | Onde | Por quê |
|---|---|---|
| `paraphrase-multilingual-mpnet-base-v2` | Estágio 2 (router) + RAG | **Já no projeto.** Forte em PT-BR. Um modelo, dois usos. Zero custo extra. |
| `pyspellchecker` | Estágio 1 | Dicionário PT-BR embutido, offline, sem serviço externo. |
| `pyahocorasick` | Estágio 3 (gazetteer) | Match de 645 municípios em O(n_texto), não O(n_municípios × n_texto). |
| `pydantic` v2 | Todos os contratos | Schema + validação + serialização num único modelo. Padrão de mercado. |
| `numpy` | Estágio 2 (cosseno) | Operação de matriz vetorizada — sub-ms para ~300 exemplos. |
| `Ollama` + `qwen2.5-3B` | Fallback | API OpenAI-compatible, modelo pequeno, só para texto livre. |
| `pytest` + `pytest-asyncio` | Testes | Cada estágio testável isolado (entradas/saídas tipadas). |
| `SQLAlchemy async` + `PostGIS` | Estágio 4 | Mantidos — são ativos do projeto, não mudam. |
| `pgvector` | RAG | Mantido — busca vetorial já está correta. |

### O que é REMOVIDO e por quê

| Removido | Por quê |
|---|---|
| `TfidfVectorizer` + `LogisticRegression` | Substituído pelo router semântico (mpnet). Sem semântica, frágil com sinônimos. |
| `training/train_data.py` (como treino) | Vira `examples/intent_examples.py` (exemplos do router). Sem retreino. |
| `*.joblib` | Não há mais modelo para serializar — os embeddings ficam em memória. |
| `DISPATCH` + `_build_tool_arguments` | Substituído por `DomainSpec` + motor genérico. |
| `_TEMPLATES` + `_STRATEGY_MAP` | Substituído por renderers por domínio em `responder.py`. |
| Motor de regras do `agent.py` (7 overrides + vocabulários `_TOKENS_*`) | A lógica de entendimento passa para o router semântico. Regra → exemplo. |
| `AdvancedGeoASGPreprocessor` (lematização/stemming na frase toda) | Substituído por `text_hygiene.py` (higiene + spell-check). |

---

## 9. Pré-processamento em detalhe (por que importa)

O pré-processamento não some — ele é **redesenhado com propósito**:

```
texto bruto
    │
    ├─ [higiene]       strip, espaços, caracteres de controle
    │
    ├─ [spell-check]   "keiimada" → "queimada"  (pyspellchecker PT-BR)
    │                  "dezmatamento" → "desmatamento"
    │
    ├─ [normalizado]   lowercase + unidecode  → usado no gazetteer (lookup no banco)
    │
    └─ [corrigido]     lowercase, acentos mantidos → enviado ao mpnet (transformer)
```

**Por que manter acentos para o transformer:**
O mpnet foi treinado com texto em português com acentuação. "São Paulo" e "sao paulo" geram
embeddings ligeiramente diferentes — o modelo usa a acentuação como sinal. Remover acentos antes
de embeddar é um anti-pattern.

**Por que normalizar (sem acento) para o gazetteer:**
O banco tem `municipio.nome_normalizado` sem acento para exatamente esse fim. O match
Aho-Corasick usa a versão normalizada, não o texto original.

---

## 10. Plano de Execução (Fases)

> Construir em pasta nova `nlp_processor_v2/` e trocar o `index.py` só na Fase 6.
> Isso garante rollback imediato se necessário.

### Fase 0 — Infra e contratos (1–2h)
- [ ] Criar estrutura de pastas
- [ ] Escrever `domain/contracts.py` completo
- [ ] Configurar `pyspellchecker`, `pyahocorasick`, `pytest-asyncio`
- [ ] Subir Ollama + baixar `qwen2.5:3b`
- **Critério:** `from domain.contracts import QuerySpec` funciona; Ollama responde

### Fase 1 — Estágio 1: Pré-processamento (2–3h)
- [ ] `pipeline/text_hygiene.py`
- [ ] `tests/unit/test_text_hygiene.py` com casos de erro ortográfico PT-BR
- **Critério:** "keiimada em campinhas" → `TextoProcessado{ corrigido="queimada em campinas" }`

### Fase 2 — Estágio 2: Router semântico (3–4h)
- [ ] Migrar `training/train_data.py` → `examples/intent_examples.py`
- [ ] `pipeline/semantic_router.py` (embed + cosseno + threshold)
- [ ] `tests/unit/test_semantic_router.py`
- **Critério:** 10 perguntas diversas roteadas corretamente; multi-intenção detectada

### Fase 3 — Estágio 3: Extrator de entidades (3–4h)
- [ ] `infrastructure/gazetteer.py` (Aho-Corasick + cache do banco)
- [ ] `pipeline/entity_extractor.py` (regex de datas, CAR, filtros; sem lógica de intenção)
- [ ] `tests/unit/test_entity_extractor.py`
- **Critério:** município, datas, CAR, bioma, categoria extraídos corretamente

### Fase 4 — Estágio 4: Motor de queries (4–6h)
- [ ] `engine/domain_spec.py` + `engine/domain_registry.py`
- [ ] `engine/query_engine.py` (motor genérico + asyncio.gather)
- [ ] Migrar 2 domínios primeiro: `QUEIMADA` e `DESMATAMENTO`
- [ ] `tests/integration/test_query_engine.py` (contra banco de teste)
- [ ] Migrar domínios restantes: UC, TI, Quilombola, Imóvel, etc.
- **Critério:** `ToolResult` de `QUEIMADA` bate com saída atual do `buscar_queimadas`

### Fase 5 — Estágio 5: Responder + Fallback LLM (2–3h)
- [ ] `pipeline/responder.py` (renderers por domínio)
- [ ] `pipeline/llm_fallback.py` (Ollama, só texto, sem structured output)
- [ ] `tests/unit/test_responder.py`
- **Critério:** texto fluente e números fiéis ao `ToolResult`

### Fase 6 — Orquestrar e ligar (2–3h)
- [ ] `orchestrator.py`
- [ ] Atualizar `index.py` para chamar `orchestrator.run`
- [ ] `tests/e2e/golden_set.py` rodando (289 perguntas)
- [ ] Shadow mode: rodar novo em paralelo ao antigo, comparar divergências no log
- **Critério:** sem regressão relevante no golden set

### Fase 7 — Limpar (1h)
- [ ] Remover `training/`, `*.joblib`, `agent.py` (motor de regras), `query_builder.py` antigo,
  `response_formatter.py` antigo, `intent_classifier.py`, `preprocessor.py`
- [ ] Atualizar `README.md` com instruções de execução

---

## 11. Como Rodar (Instruções Completas)

### Pré-requisitos de hardware
| Recurso | Mínimo | Recomendado |
|---|---|---|
| RAM | 8 GB | 16 GB |
| VRAM (GPU) | — (CPU funciona) | 6 GB (para o Ollama) |
| Disco | 10 GB livres | 20 GB |
| Python | 3.11+ | 3.11+ |

### 1. Instalar dependências Python
```bash
pip install pyspellchecker pyahocorasick pydantic numpy pytest pytest-asyncio
# sentence-transformers já deve estar instalado (RAG atual)
```

### 2. Instalar e configurar Ollama
```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Baixar modelo de fallback (pequeno, só para texto)
ollama pull qwen2.5:3b

# Verificar
ollama run qwen2.5:3b "Olá, responda em português."
```

### 3. Variáveis de ambiente (`.env`)
```env
# LLM local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

# Router semântico
CONFIDENCE_THRESHOLD=0.55
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2

# Spell-check
SPELLCHECK_LANGUAGE=pt

# Banco (já existente no projeto)
DATABASE_URL=postgresql+asyncpg://...
```

### 4. Pré-aquecer o router (ao subir o serviço)
```python
# O router embeda os exemplos no boot — não em cada requisição
await semantic_router.warm_up()
# Log esperado: "Router aquecido: 289 exemplos embeddados em 1.2s"
```

### 5. Rodar os testes
```bash
# Unitários (sem banco, sem GPU)
pytest tests/unit/ -v

# Integração (requer banco de teste)
pytest tests/integration/ -v

# End-to-end com golden set
pytest tests/e2e/ -v
```

### 6. Rodar o serviço
```bash
# Igual ao atual — a interface pública (index.py) não muda
uvicorn api.main:app --reload
```

---

## 12. Performance Esperada

| Estágio | Latência típica | Como medir |
|---|---|---|
| 1. Pré-processar | < 5 ms | `marcos["preprocess_ms"]` |
| 2. Router (warm) | < 20 ms | `marcos["router_ms"]` |
| 3. Extrair entidades | < 5 ms | `marcos["extractor_ms"]` |
| 4. Buscar (1 spec) | 50–200 ms | `marcos["query_ms"]` |
| 4. Buscar (N specs, paralelo) | ~200 ms independente de N | `asyncio.gather` |
| 5. Responder | < 10 ms | `marcos["responder_ms"]` |
| **Total (caminho feliz)** | **< 300 ms** | `marcos["total_ms"]` |
| Fallback LLM | 500–2000 ms | só acionado em < 10% das perguntas |

O **warm-up** (boot) leva ~2s para embeddar os exemplos. Depois, todos os embeddings ficam em
memória (`numpy` array) — nenhum I/O em disco por requisição.

---

## 13. Definição de Pronto (Checklist Final)

- [ ] Todos os testes unitários passando
- [ ] Todos os testes de integração passando
- [ ] Golden set com ≥ 90% de acerto no router semântico
- [ ] Pergunta simples, complexa, composta, aninhada e follow-up funcionando end-to-end
- [ ] Fallback LLM acionado corretamente para perguntas fora do escopo
- [ ] Shadow mode sem regressão relevante vs. sistema atual
- [ ] `orchestrator.py` legível em 30 segundos (máx. 20 linhas)
- [ ] Nenhum `dict` solto entre estágios (só contratos Pydantic)
- [ ] Zero lógica de intenção no extrator de entidades
- [ ] Zero lógica de banco no router semântico
- [ ] Código antigo removido (classifier, regras, dispatch, templates, training)
- [ ] README com instruções de execução completas
- [ ] Documentação de cada arquivo (docstring de módulo com responsabilidade única)

---

## Resumo em uma linha por estágio

| # | Estágio | Entrada | Saída | Tecnologia |
|---|---|---|---|---|
| 1 | Pré-processar | texto bruto | `TextoProcessado` | `pyspellchecker` + `unidecode` |
| 2 | Entender | `TextoProcessado` | `PlanoConsulta` | mpnet + cosseno |
| 3 | Extrair | `PlanoConsulta` + banco | `list[QuerySpec]` validado | Aho-Corasick + regex |
| 4 | Buscar | `list[QuerySpec]` | `list[ToolResult]` | SQLAlchemy + PostGIS |
| 5 | Responder | `list[ToolResult]` | `RespostaNLP` | renderers por domínio |
| F | Fallback | pergunta + histórico | `RespostaNLP` | Ollama `qwen2.5:3b` |

> Pergunta → **spell-check** → **mpnet entende** → **código extrai** → **motor busca**
> → **renderer compõe** → Resposta.
> Todo o processo NLP feito pela equipe. LLM só quando o sistema não tem confiança suficiente.
