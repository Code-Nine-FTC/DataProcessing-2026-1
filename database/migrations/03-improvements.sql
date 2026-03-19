-- Essencial para RAG com pgvector. HNSW > IVFFlat para datasets menores.
CREATE INDEX idx_trecho_embedding ON documento_trecho
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Substitui o campo TEXT livre por FK para intencao_consulta
ALTER TABLE consulta_usuario
  ADD COLUMN intencao_id UUID,
  ADD COLUMN intencao_score NUMERIC; -- confiança do modelo (0.0 a 1.0)

ALTER TABLE consulta_usuario
  ADD FOREIGN KEY (intencao_id) REFERENCES intencao_consulta (id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE consulta_usuario DROP COLUMN intencao_detectada;

-- Histórico de conversa por sessão
CREATE INDEX idx_consulta_chat_id ON consulta_usuario (chat_id);

-- Ordenação cronológica de mensagens
CREATE INDEX idx_consulta_data_hora ON consulta_usuario (data_hora);

-- Centralização do mapa após resposta
CREATE INDEX idx_resposta_bbox ON resposta_sistema USING GIST (bbox_resultado);

-- Lookup de respostas por consulta
CREATE INDEX idx_resposta_consulta_id ON resposta_sistema (consulta_usuario_id);

ALTER TABLE resposta_sistema
  ADD COLUMN status TEXT DEFAULT 'sucesso' 
    CHECK (status IN ('sucesso', 'erro', 'fallback', 'sem_resultado')),
  ADD COLUMN mensagem_erro TEXT; -- populado quando status != 'sucesso'

CREATE TABLE feedback_resposta (
  "id"                  UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "resposta_sistema_id" UUID NOT NULL,
  "avaliacao"           SMALLINT CHECK (avaliacao IN (-1, 0, 1)), -- -1 ruim, 0 neutro, 1 bom
  "comentario"          TEXT,
  "data_hora"           TIMESTAMP DEFAULT now(),
  FOREIGN KEY (resposta_sistema_id) REFERENCES resposta_sistema (id)
    DEFERRABLE INITIALLY IMMEDIATE
);

CREATE INDEX idx_feedback_resposta_id ON feedback_resposta (resposta_sistema_id);

CREATE TABLE rel_imovel_bacia (
  "id"                    UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id"       UUID NOT NULL,
  "bacia_hidrografica_id" INT  NOT NULL,
  "area_intersecao_ha"    NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "tipo_relacao"          TEXT, -- 'dentro', 'parcial', 'adjacente'
  FOREIGN KEY (imovel_rural_id) REFERENCES imovel_rural (id)
    DEFERRABLE INITIALLY IMMEDIATE,
  FOREIGN KEY (bacia_hidrografica_id) REFERENCES bacia_hidrografica (id)
    DEFERRABLE INITIALLY IMMEDIATE
);

ALTER TABLE documento_trecho
  ADD COLUMN tokens_count INT; -- contagem de tokens do trecho (controle de context window do LLM)

-- Garante ordenação correta de turnos dentro de um mesmo chat,
-- sem depender de data_hora (que pode ter resolução de segundos)
ALTER TABLE consulta_usuario
  ADD COLUMN turno INT;

CREATE UNIQUE INDEX idx_consulta_chat_turno ON consulta_usuario (chat_id, turno);