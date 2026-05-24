# INFORMAÇÕES AGENTE NLP

- Pipeline criada para lidar com os dados do banco
- Todos os arquivos do fluxo do NLP está com comentários para todos entenderem
- Para treinar e criar o modelo deve rodar o train.py
- O conteúdo para o treino está no train_data.py
- As rotas do chat foi adicionado na API também

### Resultados Atuais do Treinamento

- Quantidades de dados [226]
- Acurácia [97%]
- F1-macro CV 5-fold [0.841 ± 0.042]

### Observações

- Para chegar próximo de 0.90+ no CV, adicione mais exemplos em `train_data.py` e re-execute o treino

---

## Rotas da API

Base URL: `http://localhost:5000` literalmente a mesma base

---

### POST `/chat/mensagem`

Envia uma pergunta ao agente ambiental. Retorna resposta textual + GeoJSON para o mapa Leaflet.

**Body (JSON):**
```json
{
  "pergunta": "Quais foram os focos de queimada em Campinas em 2024?",
  "chat_id": null
}
```

> `chat_id` é `null` para iniciar um novo chat. Em mensagens seguintes, envie o UUID retornado para manter o histórico.

**Resposta (200):**
```json
{
  "chat_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "consulta_id": "a1b2c3d4-1234-5678-abcd-ef1234567890",
  "resposta_id": "e5f6g7h8-1234-5678-abcd-ef1234567890",
  "status": "sucesso",
  "texto_resposta": "Com base nos dados do **INPE BDQueimadas**, foram identificados **47 focos de queimada** no município de **Campinas**.\n\n**Fontes consultadas:**\n- INPE BDQueimadas (INPE)",
  "fontes_citadas": [
    {
      "nome": "INPE BDQueimadas",
      "orgao": "INPE",
      "url": "https://queimadas.dgi.inpe.br"
    }
  ],
  "bbox": [-47.5, -23.4, -46.8, -22.6],
  "qgis": {
    "crs": "EPSG:4326",
    "geojson_url_path": "/chat/resposta/e5f6g7h8-1234-5678-abcd-ef1234567890/geojson",
    "como_carregar_no_qgis": "No QGIS: Camada → Adicionar camada → Adicionar camada vetorial → em «Fonte» use a URI completa (URL base do servidor + caminho abaixo). Caminho: /chat/resposta/.... CRS da camada: WGS 84 / EPSG:4326."
  },
  "mapa": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [-47.123, -22.987]
        },
        "properties": {
          "tipo": "queimada",
          "data_ocorrencia": "2024-08-15 14:32:00",
          "fonte_sensor": "AQUA_M-T",
          "intensidade": 42.7,
          "municipio": "Campinas"
        }
      }
    ]
  }
}
```

**Valores de `status`:**

| Valor | Descrição |
|---|---|
| `sucesso` | Dados encontrados e mapa gerado |
| `sem_resultado` | Pergunta válida, mas sem dados nas fontes |
| `fora_escopo` | Pergunta fora do tema ambiental/SP |
| `erro` | Falha interna |

---

### GET `/chat/resposta/{resposta_id}/geojson`

Retorna o **mesmo GeoJSON** gravado em banco para aquela resposta (`resposta_sistema.mapa_geojson`). Use esta URL no QGIS (camada vetorial via HTTP) para não reprocessar o NLP. CRS: **EPSG:4326**. Se a resposta não existir: `404`.

---

### GET `/chat/`

Lista os últimos 50 chats criados.

**Resposta (200):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "Quais foram os focos de queimada em Campinas em 2024?"
  }
]
```

---

### GET `/chat/{chat_id}/historico`

Retorna todas as mensagens de um chat.

**Parâmetro de rota:** `chat_id` — UUID do chat

**Resposta (200):**
```json
{
  "chat_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Quais foram os focos de queimada em Campinas em 2024?",
  "mensagens": [
    {
      "consulta_id": "a1b2c3d4-...",
      "pergunta": "Quais foram os focos de queimada em Campinas em 2024?",
      "resposta": "Com base nos dados do **INPE BDQueimadas**...",
      "turno": 1,
      "qgis": {
        "crs": "EPSG:4326",
        "geojson_url_path": "/chat/resposta/e5f6g7h8-1234-5678-abcd-ef1234567890/geojson",
        "como_carregar_no_qgis": "No QGIS: use URI completa (URL base + geojson_url_path). CRS: WGS 84 / EPSG:4326."
      },
      "fontes": [
        {
          "nome": "INPE BDQueimadas",
          "orgao": "INPE",
          "url": "https://queimadas.dgi.inpe.br"
        }
      ]
    }
  ]
}
```

---

### POST `/chat/feedback`

Registra avaliação do usuário sobre uma resposta.

**Body (JSON):**
```json
{
  "resposta_sistema_id": "e5f6g7h8-1234-5678-abcd-ef1234567890",
  "avaliacao": 1,
  "comentario": "Resposta bem detalhada!"
}
```

> `avaliacao`: `1` = positivo, `0` = neutro, `-1` = negativo

**Resposta (201):**
```json
{
  "mensagem": "Feedback registrado com sucesso."
}
```

---

## Exemplos no Postman

### Configuração inicial

1. Crie uma **Collection** chamada `DataProcessing NLP`
2. Adicione uma variável de collection `base_url` = `http://localhost:5000`
3. Adicione uma variável `chat_id` (vazia inicialmente — será preenchida automaticamente)

---

### Request 1 — Novo chat (queimadas)

- **Método:** `POST`
- **URL:** `{{base_url}}/chat/mensagem`
- **Headers:** `Content-Type: application/json`
- **Body (raw JSON):**
```json
{
  "pergunta": "Quais foram os focos de queimada em Campinas em 2024?",
  "chat_id": null
}
```
- **Tests (salvar chat_id automaticamente):**
```javascript
const res = pm.response.json();
pm.collectionVariables.set("chat_id", res.chat_id);
pm.test("Status sucesso", () => pm.expect(res.status).to.eql("sucesso"));
```

---

### Request 2 — Continuar conversa (desmatamento)

- **Método:** `POST`
- **URL:** `{{base_url}}/chat/mensagem`
- **Body (raw JSON):**
```json
{
  "pergunta": "E alertas de desmatamento na mesma região?",
  "chat_id": "{{chat_id}}"
}
```

---

### Request 3 — Listar chats

- **Método:** `GET`
- **URL:** `{{base_url}}/chat/`

---

### Request 4 — Ver histórico

- **Método:** `GET`
- **URL:** `{{base_url}}/chat/{{chat_id}}/historico`

---

### Request 5 — Enviar feedback

- **Método:** `POST`
- **URL:** `{{base_url}}/chat/feedback`
- **Body (raw JSON):**
```json
{
  "resposta_sistema_id": "cole-aqui-o-resposta_id-retornado",
  "avaliacao": 1,
  "comentario": "Dados bem detalhados"
}
```

---

### Perguntas de exemplo para testar

```
Quais são as unidades de conservação em Ubatuba?
Terras indígenas homologadas no litoral sul paulista
Assentamentos do INCRA no Pontal do Paranapanema
Territórios quilombolas no Vale do Ribeira
Imóveis rurais com CAR ativo em Sorocaba
O que é o Código Florestal?
Queimadas no Pantanal mato-grossense
```

> A última pergunta deve retornar `status: fora_escopo` pois é de outro estado.