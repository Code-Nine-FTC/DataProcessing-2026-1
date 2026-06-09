# Módulo NLP — Atlas Ambiental SP

Este documento explica, de ponta a ponta, como o módulo `nlp_processor` transforma uma
**pergunta em linguagem natural** numa **resposta textual + mapa GeoJSON**. É voltado tanto
para a equipe de desenvolvimento quanto para um leitor técnico que precise entender as decisões
de arquitetura, os tipos/níveis de resposta e os pontos de extensão.

> O sistema é especializado no **estado de São Paulo** e em dados **ambientais e territoriais**:
> queimadas, desmatamento, unidades de conservação, terras indígenas, territórios quilombolas,
> assentamentos rurais, imóveis rurais (CAR) e documentos de referência (RAG).

---

## 1. Visão geral da arquitetura

O módulo é uma **pipeline determinística orientada a registries**, e não um "agente LLM" de
chamada de ferramentas. Cada etapa tem responsabilidade única (SRP) e as capacidades são
declaradas em tabelas (dicionários), não em `if/else` espalhados. Isso é o que torna o sistema
**escalável**: adicionar um novo tipo de dado é adicionar uma função + 3 entradas de registro,
sem tocar na orquestração.

```
                          ┌──────────────────────────────────────────────────────┐
   POST /chat/mensagem     │                     index.py                          │
   { pergunta, chat_id } ─▶│  carrega/cria chat → histórico → run_agent →          │
                          │  persiste consulta+resposta → monta GeoJSON+bbox      │
                          └───────────────────────────┬──────────────────────────┘
                                                      │
                                                      ▼
                          ┌──────────────────────────────────────────────────────┐
                          │                      agent.py                          │
                          │  1. preprocessor.process(pergunta)                     │
                          │  2. _montar_plano  (segmentação multi-intenção)        │
                          │       ├─ intent_classifier.predict                     │
                          │       ├─ entity_extractor.extrair_entidades            │
                          │       └─ _resolver_intencao_final                      │
                          │  3. embedder.embed   (somente se needs_rag)            │
                          │  4. query_builder.executar_plano                       │
                          │  5. response_formatter.compor_resposta                 │
                          │  6. fusão de features/bbox/fontes + status             │
                          └───────────────────────────┬──────────────────────────┘
                                                      │
              ┌───────────────────────────────────────┼───────────────────────────────────┐
              ▼                                       ▼                                   ▼
   pipeline/preprocessor.py            pipeline/query_builder.py            pipeline/response_formatter.py
   pipeline/intent_classifier.py       tools.py (consultas PostGIS/RAG)
   pipeline/entity_extractor.py
   pipeline/embedder.py
```

### Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `index.py` | **Orquestrador de aplicação.** Chat, histórico, chamada do agente, persistência no banco, montagem do GeoJSON/bbox final. É o contrato com a API. |
| `agent.py` | **Cérebro do NLP.** Pré-processa, monta o **plano de tarefas** (multi-intenção), resolve a intenção, decide se usa RAG, executa o plano e compõe a resposta. |
| `pipeline/preprocessor.py` | **Limpeza léxica + linguística** (spaCy). Gera o texto normalizado usado por todas as etapas seguintes. |
| `pipeline/intent_classifier.py` | **Classificador de intenção** (TF-IDF + Regressão Logística). Retorna `(intenção, confiança)`. |
| `pipeline/entity_extractor.py` | **Extração de entidades** por regex/gazetteer (município, datas, CAR, bioma, contexto espacial, temas de ranking/sobreposição…). |
| `pipeline/embedder.py` | **Embeddings** (`mpnet`, 768d) para a busca documental (RAG). |
| `pipeline/query_builder.py` | **Despacho e execução.** Mapeia intenção→ferramenta, executa as tarefas (em paralelo quando possível) e roda o RAG sob demanda. |
| `tools.py` | **Ferramentas de consulta.** Funções `async` que executam o SQL/PostGIS de cada capacidade e retornam features GeoJSON + metadados. |
| `pipeline/response_formatter.py` | **Geração de texto.** Renderiza um bloco por resultado e compõe a resposta final com citação de fontes. |
| `training/` | **Treino do classificador** (`train.py`, `train_data.py`). |
| `models/` | Artefatos treinados (`*.joblib`). |

---

## 2. Fluxo ponta a ponta (do prompt à resposta)

### Etapa 0 — Entrada (API → `index.py`)

A rota `POST /chat/mensagem` recebe `{ "pergunta": str, "chat_id": uuid|null }`.
`NLPProcessor.process()`:

1. **Carrega ou cria o chat** (`_load_or_create_chat`).
2. **Carrega o histórico** dos últimos turnos (`_load_historico`, máx. `HISTORICO_MAX_TURNOS = 10`),
   incluindo a avaliação de feedback de cada resposta — isso alimenta o ajuste por feedback.
3. Chama **`run_agent(...)`** (o núcleo).
4. Persiste a consulta e a resposta, calcula o **bbox**, monta o **GeoJSON** e devolve o payload final.

### Etapa 1 — Pré-processamento (`preprocessor.py`)

`AdvancedGeoASGPreprocessor.process()` aplica, em ordem, etapas léxicas e linguísticas:

1. Proteção de vírgulas decimais (ex.: `5,70`).
2. **Correção ortográfica / gírias** (`pyspellchecker` + mapa de abreviações).
3. Substituição de emojis/emoticons por rótulos (`🔥` → `queimada incendio`).
4. Anonimização de menções `@usuario`.
5. Remoção de URLs.
6. Restauração das vírgulas decimais.
7. Limpeza de pontuação **preservando** datas, hashtags, decimais e **código CAR**; remoção de acentos.
8. **spaCy** (`pt_core_news_sm`): tokenização, POS tagging, lematização e remoção de stopwords.

Saída relevante:
- `text_for_entities_and_rag` — **texto normalizado** (sem acento, minúsculo após `.lower()`),
  usado por **classificador, extrator de entidades e RAG**.
- `text_for_classifier` — texto lematizado (disponível, mas o classificador atual usa o normalizado).

> **Cuidado conhecido (robustez):** o corretor ortográfico pode corromper termos do domínio
> ausentes do dicionário pt (ex.: `desmatamento`→`desatamento`, `ranking`→`rafting`). Por isso há
> um **léxico protegido** (`_LEXICO_DOMINIO` + `system_vocabulary`) e os **nomes próprios
> capitalizados não são corrigidos** (guarda `word != word.lower()`, protege "Ubatuba" etc.).
> Ao depurar uma resposta estranha, **imprima `text_for_entities_and_rag` primeiro.**

### Etapa 2 — Montagem do plano de tarefas (`agent._montar_plano`)

Esta é a peça que permite responder perguntas **simples e com duas ou mais intenções**.

1. Extrai as **entidades da pergunta inteira** (escopo compartilhado: município, RA, datas).
2. Resolve a **intenção geral** com `_resolver_intencao_final` (ver Seção 4).
3. Decide se a pergunta é **holística** (tratada como **uma** tarefa) quando:
   - a intenção é holística (`sobreposição`, `ranking`, `passivos`, `focos por imóvel`, `fora_escopo`), **ou**
   - há **código CAR**, **ou**
   - **não há conector** na frase.
4. Caso contrário, **segmenta** a pergunta por conectores (`_CONECTORES_RE`: `" e "`, `";"`,
   `"também"`, `"além de"`, `"bem como"`, `"assim como"`) e, para **cada segmento**:
   - extrai entidades **sem reprocessar spaCy** (usa o texto já normalizado),
   - **herda o escopo** compartilhado (município/datas) quando o segmento não o traz (`_herdar_escopo`),
   - resolve a intenção do segmento,
   - descarta `fora_escopo` e duplicatas.

> **Por que holístico?** "Sobreposição **entre** TI **e** UC" contém um `" e "`, mas **não** deve
> ser quebrada — é uma única análise. A regra holística protege esses casos antes da segmentação.

Resultado: uma lista `[(intenção, entidades), ...]` — o **plano**.

### Etapa 3 — Embedding sob demanda (RAG)

O embedding (`mpnet`, ~50–200 ms) **só é gerado quando há a intenção `buscar_documentos`**
(`needs_rag`). Perguntas de dados (queimada, desmatamento, sobreposição…) **não pagam** esse custo.

### Etapa 4 — Execução do plano (`query_builder.executar_plano`)

1. Se `needs_rag`, roda a **busca documental (RAG) uma única vez**.
2. Executa as tarefas:
   - **1 tarefa** → execução direta na sessão atual.
   - **2+ tarefas** → execução **paralela** com `asyncio.gather` e **uma sessão por tarefa**
     (`session_factory`), porque um `AsyncSession` não é seguro para consultas concorrentes.
3. Para cada tarefa, resolve a ferramenta via **tabela de despacho 2D** `DISPATCH[(intent, contexto_espacial)]`,
   monta os argumentos (`_build_tool_arguments`) e chama a função em `tools.py`.
4. Devolve **um bloco por tarefa** (`effective_tool`, `features`, `bbox`, `fontes`, `descricao`).

### Etapa 5 — Composição da resposta (`response_formatter.compor_resposta`)

- Renderiza **um bloco de texto por resultado** (`_render_bloco`), escolhendo:
  - **template** específico da ferramenta (`_TEMPLATES`), **ou**
  - **estratégia especializada** (`_STRATEGY_MAP`) para casos que precisam montar listas
    (ranking, passivos por imóvel, imóveis afetados, sobreposição), **ou**
  - **mensagem de "sem resultado"** quando `total_features == 0`.
- Concatena os blocos e adiciona **um único rodapé de fontes deduplicado**.
- Aplica o **ajuste por feedback** do turno anterior (ver Seção 6), se houver.

### Etapa 6 — Fusão e retorno (`agent.run_agent` → `index.py`)

`run_agent` **funde** os blocos mantendo o **mesmo contrato de saída** de sempre:
- `features` = união de todas as features (um só GeoJSON para o mapa),
- `bbox` = união dos bounding boxes,
- `fontes` = união deduplicada,
- `intencao` = intenções unidas por `+` (ex.: `buscar_queimadas+buscar_desmatamentos`),
- `status` = ver Seção 3.

`index.py` persiste e devolve o payload com `texto_resposta`, `fontes_citadas`, `mapa` (GeoJSON),
`bbox` e `status`.

---

## 3. Níveis / tipos de resposta (status) e como são definidos

Toda resposta carrega um **`status`** que diz à API/front como tratá-la. Ele é calculado em
`agent._status_do_plano` (e `index.py` reage a ele):

| Status | Quando ocorre | Como é decidido |
|---|---|---|
| **`sucesso`** | Há dados e/ou contexto documental relevante | Algum bloco tem `features`, **ou** há `document_context` (RAG). |
| **`sem_resultado`** | Pergunta válida, mas sem dados nas fontes | Nenhum bloco tem features e não há contexto documental. `index.py` lança `DataNotFoundError`. |
| **`fora_escopo`** | Pergunta fora do tema/estado | Todos os blocos são `fora_escopo`. Resposta = template explicativo de escopo. |
| **`erro`** | Falha interna (modelo não carregado, exceção no banco) | `_build_resultado_erro`. `index.py` lança `NLPProcessingError`. |

Além do **status**, existem **níveis de elaboração** do texto da resposta:

1. **Resposta simples (template)** — 1 ferramenta, 1 frase parametrizada
   (ex.: "Com base nos dados do **INPE BDQueimadas**, foram identificados **N focos**…").
2. **Resposta estruturada (estratégia)** — listas montadas a partir das features
   (ranking municipal, passivos de um imóvel, imóveis afetados, ranking de sobreposição).
3. **Resposta documental (RAG)** — texto baseado em trechos recuperados da base de conhecimento,
   **com limiar de relevância** (abaixo dele, devolve "não encontrei conteúdo relevante").
4. **Resposta composta (multi-intenção)** — vários blocos dos tipos acima concatenados,
   com rodapé único de fontes.
5. **Resposta de escopo** — mensagem padrão quando a pergunta é fora do escopo.

---

## 4. Resolução de intenção (`agent._resolver_intencao_final`)

A intenção final é decidida por uma **ordem de prioridade explícita** — combinando o classificador
de ML com sinais de vocabulário (mais robustos quando os dados de treino são escassos):

1. **Fora de escopo** — `_fora_escopo`: sem município/RA/CAR de SP **e** (cita estado/região fora
   de SP **ou** não tem nenhum token ambiental). Detecta "Bahia", "Pantanal mato-grossense" etc.
2. **Override por código CAR** — se há CAR, o contexto é inequivocamente de imóvel rural
   (passivos / focos no imóvel / dados do imóvel).
3. **Sobreposição entre duas camadas** — se há dois temas territoriais + termo de sobreposição
   ("sobreposição", "interseção", "cruzamento") → `buscar_sobreposicao_areas`.
4. **Ranking municipal** — superlativo ("maior", "ranking", "top") + escopo municipal →
   `buscar_maiores_quantidades` (independente da confiança).
5. **Baixa confiança (`< CONFIDENCE_THRESHOLD = 0.20`)** — usa **vocabulário**; se o vocabulário
   nada indicar, mantém a predição do classificador (quando há município) ou cai em `buscar_documentos`.
6. **Promoção de imóvel** — texto sem CAR mas mencionando "imóvel/fazenda/propriedade" + tema.
7. **Intenção do classificador** — aceita a predição como veio.

> Esse desenho é o que **amortece a fraqueza do classificador**: mesmo que o modelo erre numa
> classe com poucos exemplos, vocabulário/heurísticas cobrem o caso.

### Intenções e despacho

As intenções válidas estão em `intent_classifier.VALID_INTENTS`. O **mapa de despacho 2D**
(`query_builder.DISPATCH`) traduz `(intenção, contexto_espacial)` → ferramenta concreta em `tools.py`.
O `contexto_espacial` (de `entity_extractor`) tem valores `unidade_conservacao | terra_indigena |
quilombola | assentamento | None` e seleciona as **cross-queries** (ex.: queimadas **dentro de** UCs).

> Observação: `buscar_sobreposicao_areas` é resolvida pela **camada heurística/entidades**, não pelo
> classificador (não está em `VALID_INTENTS` nem no dataset de treino). Funciona porque é tratada
> como intenção holística por vocabulário.

---

## 5. Tipos de pergunta que o sistema responde

| Tipo | Exemplo | Ferramenta(s) |
|---|---|---|
| **Simples por tema** | "Focos de queimada em Campinas em 2024" | `buscar_queimadas` |
| **Cross-query espacial** | "Queimadas dentro de unidades de conservação" | `buscar_queimadas_em_unidades_conservacao` (etc.) |
| **Dados territoriais** | "Unidades de conservação em Ubatuba" | `buscar_unidades_conservacao`, `buscar_terras_indigenas`, … |
| **Imóvel rural / CAR** | "Imóvel SP-3500709-…" | `buscar_imoveis_rurais` / `buscar_focos_queimada_imovel` / `buscar_passivos_em_imovel` |
| **Imóveis afetados** | "Quais imóveis têm queimadas?" | `buscar_imoveis_por_queimada` (etc.) |
| **Ranking municipal** | "Municípios com mais desmatamento" | `buscar_maiores_quantidades` |
| **Sobreposição entre camadas** | "Sobreposição entre TI e UC por município" | `buscar_sobreposicao_areas` |
| **Documental (RAG)** | "O que é o Código Florestal?" | `buscar_documentos_rag` |
| **Multi-intenção** | "Queimadas **e** desmatamento em Campinas" | várias, compostas |
| **Fora de escopo** | "Queimadas no Pantanal mato-grossense" | resposta de escopo |

---

## 6. Memória de conversa e ajuste por feedback

- O **histórico** é carregado por `index.py` e passado ao agente.
- `agent._extrair_feedback_contexto` lê a **avaliação** (`-1` / `1`) da última resposta do
  assistente. Se válida (mesma intenção e dentro de `FEEDBACK_VALIDADE_MINUTOS = 30`), o
  `response_formatter` **prefixa** a resposta reconhecendo o feedback (reformular após negativo /
  manter linha após positivo).

---

## 7. Camada de dados (`tools.py`)

Cada ferramenta é uma função `async` que:
- monta uma consulta **SQLAlchemy + PostGIS** (recortando/filtrando ao estado de SP via `ST_Intersects`),
- converte geometrias para **GeoJSON em EPSG:4326** (`ST_AsGeoJSON`, com simplificação para polígonos complexos),
- retorna `{ total, features, bbox, fontes, descricao, sql_executado }`.

Casos especiais:
- **`buscar_sobreposicao_areas`** rankeia municípios pela **área de interseção** entre dois temas
  (`ST_Intersection` recortada ao município, área em EPSG:31983). Funciona para qualquer par
  (UC, TI, quilombola, assentamento, imóvel) declarado em `_OVERLAP_THEMES`.
- **`buscar_documentos_rag`** faz busca vetorial no **pgvector** por **distância cosseno (`<=>`)** e
  aplica `RELEVANCIA_MINIMA_RAG = 0.30` — trechos abaixo disso são descartados (evita devolver
  metadados de dataset irrelevantes).

O **registry `TOOL_FUNCTIONS`** (nome → função) é o ponto único de inscrição de novas ferramentas.

---

## 8. Otimizações de latência (alvo ≤ 8 s, mirando o mínimo)

1. **RAG sob demanda** — embedding só roda para `buscar_documentos`.
2. **Sem spaCy/corretor por segmento** — spaCy roda 1× na pergunta inteira; segmentos usam só
   regex + TF-IDF (sub-ms).
3. **Consultas em paralelo** — 2+ tarefas executam concorrentemente, uma sessão por tarefa
   (tempo ≈ `max(query)` em vez de `soma`).
4. **Instrumentação** — `run_agent` loga `Tempos NLP (ms)` por etapa (`preprocess`, `plano`,
   `embedding`, `consultas`, `total`) para medição real.

> O gargalo de tempo real costuma ser o **PostGIS** (joins espaciais), não a camada NLP. A query de
> sobreposição/ranking é a candidata a estourar tempo — depende de **índices GiST** nas geometrias.

---

## 9. Escalabilidade

A escalabilidade vem de **iterar sobre registries**, não de ramificar a lógica:

- **Novo tipo de dado** = 1 função em `tools.py` + entradas em `TOOL_FUNCTIONS`, `DISPATCH` e
  `_TEMPLATES`. A orquestração não muda (princípio Open/Closed).
- **Combinações multi-tema** são tratadas por iteração no plano — o custo de código é **O(1) por
  ferramenta**, não O(2ⁿ) por combinação.
- A camada NLP é **stateless** (modelos e caches como singletons) → escala **horizontalmente**.

---

## 10. Treinamento do classificador (`training/`)

- `train_data.py` — dataset `(texto, intenção)`.
- `train.py` — TF-IDF de **palavra (1,2)** + **caractere `char_wb` (3,5)** → Regressão Logística
  (`class_weight="balanced"`), validação cruzada 5-fold, salva `vectorizer.joblib` e
  `intent_classifier.joblib`.

Rodar:
```bash
python -m nlp_processor.training.train
```

> O texto de treino e o de inferência usam o **mesmo campo** (`text_for_entities_and_rag`), o que
> garante consistência e é compatível com a classificação por segmento (sem spaCy).

---

## 11. Limitações conhecidas / próximos passos

- **Base documental (RAG)** contém hoje **descrições de datasets**, não textos legais. Perguntas de
  legislação só serão respondidas de fato após **ingerir documentos reais** (SNUC, Código Florestal,
  resoluções CONAMA) em `Documento`/`DocumentoTrecho`. O limiar de relevância evita respostas enganosas.
- **Classificador** com dataset pequeno (~289 exemplos / 18 classes): F1-macro ~0,63. Próximo salto:
  expandir o dataset (classes fracas + `buscar_sobreposicao_areas`) e/ou trocar TF-IDF por um
  classificador baseado em **embeddings** (reusando o `mpnet`).
- **Contagens com `LIMIT`**: tools de listagem reportam `len(features)` limitado (ex.: 500). Para o
  total real seria necessária uma consulta `COUNT(*)` dedicada.
- **`fora_escopo` para perguntas documentais legítimas** sem token ambiental explícito (ex.:
  "Código Florestal") pode classificar como fora de escopo, pois `_fora_escopo` roda antes do
  classificador.

---

## 12. Referência rápida da API

As rotas (`POST /chat/mensagem`, `GET /chat/...`, `POST /chat/feedback`) e os exemplos de payload
estão documentados em [`INTRUCAONLP.md`](./INTRUCAONLP.md). Em resumo, `POST /chat/mensagem` recebe
`{ pergunta, chat_id }` e devolve `{ texto_resposta, fontes_citadas, mapa (GeoJSON), bbox, status }`.
