# Regras do projeto e integração QGIS

Documentação complementar: fluxo de chat, histórico e uso do GeoJSON no QGIS **sem** rota HTTP dedicada só para GeoJSON.

## Regras gerais

1. **Escopo.** O agente ambiental e as consultas espaciais refletem os dados carregados no banco, com foco no contexto de **São Paulo** quando aplicável.
2. **CRS.** O GeoJSON em `mapa` está em **WGS 84 (EPSG:4326)**.
3. **Persistência.** Cada resposta grava `mapa_geojson` em `resposta_sistema`. O histórico lê esses dados; não é necessário reexecutar o NLP para reexibir o mapa de um turno antigo.
4. **Continuidade do chat.** Envie o mesmo `chat_id` em `POST /chat/mensagem` para manter turnos e contexto.

## Rotas relevantes

| Método | Caminho | Uso |
|--------|---------|-----|
| `POST` | `/chat/mensagem` | Nova pergunta; resposta inclui `mapa`, `bbox`, `qgis`. |
| `GET` | `/chat/{chat_id}/historico` | Lista `mensagens`; **cada** mensagem com resposta inclui `mapa` e `qgis`. No nível raiz, `mapa`/`bbox`/`status` repetem a **última** resposta (útil para o mapa atual). |

Não existe `GET /chat/resposta/{id}/geojson`. O GeoJSON vem embutido no JSON (`mapa`).

## Objeto `qgis`

Presente em `POST /chat/mensagem` e em cada item de `mensagens` no histórico (quando há resposta). Contém:

- `crs`: normalmente `EPSG:4326`.
- `como_carregar_no_qgis`: passos resumidos (arquivo `.geojson` a partir do campo `mapa`).

## QGIS: fluxo recomendado

1. Chame `GET /chat/{chat_id}/historico` (ou use o `mapa` da última `POST /chat/mensagem`).
2. Escolha o turno em `mensagens[n]` e copie o valor de `mapa` (objeto `FeatureCollection`).
3. Grave em um arquivo texto com extensão `.geojson`, codificação UTF-8.
4. No QGIS: **Camada → Adicionar camada → Adicionar camada vetorial** e selecione o arquivo. Defina o CRS como **EPSG:4326** se solicitado.

Para automação, um cliente pode serializar apenas `mensagens[n].mapa` em disco ou repassar ao QGIS via script; a API não expõe URL “só GeoJSON” por desenho atual do produto.

## Referências no repositório

- Rotas FastAPI: `api/router/chat.py`
- Esquemas: `api/schemas/chat.py`
- Texto de integração: `api/utils/qgis_integracao.py`
- Detalhes adicionais da API de chat e NLP: `nlp_processor/INTRUCAONLP.md`
