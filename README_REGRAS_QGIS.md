# Regras do projeto e integração QGIS

Documentação complementar: fluxo de chat, histórico e uso do GeoJSON no QGIS.

## Regras gerais

1. **Escopo.** O agente ambiental e as consultas espaciais refletem os dados carregados no banco, com foco no contexto de **São Paulo** quando aplicável.
2. **CRS.** O GeoJSON em `mapa` está em **WGS 84 (EPSG:4326)**.
3. **Persistência.** Cada resposta grava `mapa_geojson` em `resposta_sistema`. O histórico lê esses dados; não é necessário reexecutar o NLP para reexibir o mapa de um turno antigo.
4. **Continuidade do chat.** Envie o mesmo `chat_id` em `POST /chat/mensagem` para manter turnos e contexto.

## Fluxo de dados (importante para o QGIS)

Você **não** envia GeoJSON no cliente. O fluxo é:

1. Envie **texto** em `POST /chat/mensagem` (`pergunta` e, se for continuação, o mesmo `chat_id`).
2. O servidor processa a pergunta, consulta o banco, monta o mapa e grava o GeoJSON em `resposta_sistema`.
3. A resposta traz **`resposta_id`** e o bloco **`qgis`** (inclui `geojson_url_path`). Esse id identifica **aquela** resposta — um chat tem várias respostas (uma por pergunta).
4. Para o QGIS via HTTP, use a URL **`GET /chat/resposta/{resposta_id}/geojson`** com o `resposta_id` da rodada desejada (o da última `POST` ou o de uma entrada do histórico).

**Só `chat_id`** serve para continuar a conversa ou para `GET /chat/{chat_id}/historico`. Para carregar uma camada no QGIS por URL, use sempre o **`resposta_id`** da rodada correta, não apenas o `chat_id`.

## Rotas relevantes

| Método | Caminho | Uso |
|--------|---------|-----|
| `POST` | `/chat/mensagem` | Nova pergunta; resposta inclui `resposta_id`, `mapa`, `bbox`, `qgis` (`geojson_url_path`). |
| `GET` | `/chat/resposta/{resposta_id}/geojson` | Mesmo GeoJSON persistido daquela resposta (adequado ao QGIS como fonte vetorial via URI). |
| `GET` | `/chat/{chat_id}/historico` | Lista `mensagens`; cada item com resposta inclui `resposta_id`, `mapa` e `qgis`. No nível raiz, `mapa`/`bbox`/`status` repetem a **última** resposta. |

## Objeto `qgis`

Presente em `POST /chat/mensagem` e em cada item de `mensagens` no histórico (quando há resposta). Contém:

- `crs`: normalmente `EPSG:4326`.
- `geojson_url_path`: caminho relativo, por exemplo `/chat/resposta/<uuid>/geojson` (prefixe com a URL base da API).
- `como_carregar_no_qgis`: passos resumidos (URI completa ou arquivo `.geojson` a partir do campo `mapa`).

## QGIS: fluxo recomendado

1. Obtenha o `resposta_id` da rodada que você quer (resposta do `POST /chat/mensagem` ou campo `resposta_id` em `mensagens[n]` no `GET /chat/{chat_id}/historico`).
2. Monte a URI: **URL base da API** + **`qgis.geojson_url_path`** (equivale a `GET /chat/resposta/{resposta_id}/geojson`).
3. No QGIS: **Camada → Adicionar camada → Adicionar camada vetorial** → em «Fonte» use essa URI. CRS da camada: **EPSG:4326** se solicitado.

Alternativa sem HTTP: copie o objeto `mapa` (ou `mensagens[n].mapa`), grave como arquivo `.geojson` em UTF-8 e abra o arquivo no QGIS.

## Referências no repositório

- Rotas FastAPI: `api/router/chat.py`
- Esquemas: `api/schemas/chat.py`
- Texto de integração: `api/utils/qgis_integracao.py`
- Detalhes adicionais da API de chat e NLP: `nlp_processor/INTRUCAONLP.md`
