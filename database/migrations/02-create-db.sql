CREATE TABLE "fonte_dado" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "nome" TEXT NOT NULL,
  "orgao_responsavel" TEXT,
  "url_origem" TEXT,
  "formato" TEXT,
  "periodicidade" TEXT,
  "escopo_geografico" TEXT,
  "licenca" TEXT,
  "ativo" BOOLEAN DEFAULT true
);

CREATE TABLE "dataset" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "fonte_dado_id" UUID,
  "nome" TEXT NOT NULL,
  "descricao" TEXT,
  "versao" TEXT,
  "data_coleta" TIMESTAMP,
  "data_referencia" DATE,
  "hash_arquivo" TEXT,
  "caminho_arquivo" TEXT,
  "metadata_json" JSONB
);

CREATE TABLE "processamento" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "dataset_id" UUID,
  "tipo_processamento" TEXT,
  "data_execucao" TIMESTAMP,
  "status" TEXT,
  "log_execucao" TEXT,
  "parametros_json" JSONB
);

CREATE TABLE "estado" (
  "id" SERIAL PRIMARY KEY,
  "sigla" "VARCHAR(2)",
  "nome" TEXT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)"
);

CREATE TABLE "municipio" (
  "id" SERIAL PRIMARY KEY,
  "codigo_ibge" "VARCHAR(10)",
  "nome" TEXT,
  "estado_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)"
);

CREATE TABLE "grade_espacial" (
  "id" SERIAL PRIMARY KEY,
  "codigo" TEXT,
  "resolucao" TEXT,
  "geom" "GEOMETRY(POLYGON,4326)"
);

CREATE TABLE "bacia_hidrografica" (
  "id" SERIAL PRIMARY KEY,
  "nome" TEXT,
  "codigo" TEXT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)"
);

CREATE TABLE "imovel_rural" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "nome_imovel" TEXT,
  "codigo_car" TEXT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "situacao_cadastral" TEXT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "centroid" "GEOMETRY(POINT,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "queimada_evento" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "data_ocorrencia" TIMESTAMP,
  "fonte_sensor" TEXT,
  "intensidade" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(POINT,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "desmatamento_alerta" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "data_ocorrencia" DATE,
  "tipo_alerta" TEXT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "unidade_conservacao" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "nome" TEXT,
  "categoria" TEXT,
  "esfera" TEXT,
  "grupo_snuc" TEXT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "terra_indigena" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "nome" TEXT,
  "fase" TEXT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "assentamento_rural" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "nome" TEXT,
  "modalidade" TEXT,
  "familias" INT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "territorio_quilombola" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "nome" TEXT,
  "status_processo" TEXT,
  "area_ha" NUMERIC,
  "municipio_id" INT,
  "geom" "GEOMETRY(MULTIPOLYGON,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "camada_estadual_ambiental" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "id_origem" TEXT,
  "dataset_id" UUID,
  "tema" TEXT,
  "subtipo" TEXT,
  "nome" TEXT,
  "municipio_id" INT,
  "geom" "GEOMETRY(GEOMETRYCOLLECTION,4326)",
  "atributos_json" JSONB
);

CREATE TABLE "rel_imovel_queimada" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "queimada_evento_id" UUID,
  "distancia_m" NUMERIC,
  "dentro_imovel" BOOLEAN,
  "data_calculo" TIMESTAMP
);

CREATE TABLE "rel_imovel_desmatamento" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "desmatamento_alerta_id" UUID,
  "area_intersecao_ha" NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "data_calculo" TIMESTAMP
);

CREATE TABLE "rel_imovel_uc" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "unidade_conservacao_id" UUID,
  "area_intersecao_ha" NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "tipo_relacao" TEXT
);

CREATE TABLE "rel_imovel_ti" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "terra_indigena_id" UUID,
  "area_intersecao_ha" NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "tipo_relacao" TEXT
);

CREATE TABLE "rel_imovel_assentamento" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "assentamento_rural_id" UUID,
  "area_intersecao_ha" NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "tipo_relacao" TEXT
);

CREATE TABLE "rel_imovel_quilombo" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "imovel_rural_id" UUID,
  "territorio_quilombola_id" UUID,
  "area_intersecao_ha" NUMERIC,
  "percentual_sobreposicao" NUMERIC,
  "tipo_relacao" TEXT
);

CREATE TABLE "conceito" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "nome_canonico" TEXT,
  "tipo_conceito" TEXT
);

CREATE TABLE "conceito_alias" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "conceito_id" UUID,
  "alias" TEXT
);

CREATE TABLE "intencao_consulta" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "nome" TEXT,
  "descricao" TEXT
);

CREATE TABLE "documento" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "dataset_id" UUID,
  "titulo" TEXT,
  "tipo" TEXT,
  "texto_integral" TEXT,
  "url_origem" TEXT,
  "metadata_json" JSONB
);

CREATE TABLE "documento_trecho" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "documento_id" UUID,
  "ordem" INT,
  "texto" TEXT,
  "embedding" "VECTOR(768)"
);

CREATE TABLE "chat" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "title" TEXT,
  "created_at" TIMESTAMP
);

CREATE TABLE "consulta_usuario" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "pergunta" TEXT,
  "data_hora" TIMESTAMP,
  "intencao_detectada" TEXT,
  "entidades_detectadas_json" JSONB,
  "filtros_detectados_json" JSONB,
  "chat_id" UUID
);

CREATE TABLE "resposta_sistema" (
  "id" UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
  "consulta_usuario_id" UUID,
  "texto_resposta" TEXT,
  "sql_executado" TEXT,
  "fontes_utilizadas_json" JSONB,
  "bbox_resultado" "GEOMETRY(POLYGON,4326)",
  "tempo_resposta_ms" INT
);

CREATE INDEX "idx_estado_geom" ON "estado" USING GIST ("geom");

CREATE INDEX "idx_municipio_geom" ON "municipio" USING GIST ("geom");

CREATE INDEX "idx_grade_geom" ON "grade_espacial" USING GIST ("geom");

CREATE INDEX "idx_bacia_geom" ON "bacia_hidrografica" USING GIST ("geom");

CREATE INDEX "idx_imovel_geom" ON "imovel_rural" USING GIST ("geom");

CREATE INDEX "idx_queimada_geom" ON "queimada_evento" USING GIST ("geom");

CREATE INDEX "idx_desmatamento_geom" ON "desmatamento_alerta" USING GIST ("geom");

CREATE INDEX "idx_uc_geom" ON "unidade_conservacao" USING GIST ("geom");

CREATE INDEX "idx_ti_geom" ON "terra_indigena" USING GIST ("geom");

CREATE INDEX "idx_assentamento_geom" ON "assentamento_rural" USING GIST ("geom");

CREATE INDEX "idx_quilombo_geom" ON "territorio_quilombola" USING GIST ("geom");

CREATE INDEX "idx_camada_geom" ON "camada_estadual_ambiental" USING GIST ("geom");

ALTER TABLE "dataset" ADD FOREIGN KEY ("fonte_dado_id") REFERENCES "fonte_dado" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "processamento" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "municipio" ADD FOREIGN KEY ("estado_id") REFERENCES "estado" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "imovel_rural" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "imovel_rural" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "queimada_evento" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "queimada_evento" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "desmatamento_alerta" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "desmatamento_alerta" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "unidade_conservacao" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "unidade_conservacao" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "terra_indigena" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "terra_indigena" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "assentamento_rural" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "assentamento_rural" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "territorio_quilombola" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "territorio_quilombola" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "camada_estadual_ambiental" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "camada_estadual_ambiental" ADD FOREIGN KEY ("municipio_id") REFERENCES "municipio" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_queimada" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_queimada" ADD FOREIGN KEY ("queimada_evento_id") REFERENCES "queimada_evento" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_desmatamento" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_desmatamento" ADD FOREIGN KEY ("desmatamento_alerta_id") REFERENCES "desmatamento_alerta" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_uc" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_uc" ADD FOREIGN KEY ("unidade_conservacao_id") REFERENCES "unidade_conservacao" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_ti" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_ti" ADD FOREIGN KEY ("terra_indigena_id") REFERENCES "terra_indigena" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_assentamento" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_assentamento" ADD FOREIGN KEY ("assentamento_rural_id") REFERENCES "assentamento_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_quilombo" ADD FOREIGN KEY ("imovel_rural_id") REFERENCES "imovel_rural" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rel_imovel_quilombo" ADD FOREIGN KEY ("territorio_quilombola_id") REFERENCES "territorio_quilombola" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "conceito_alias" ADD FOREIGN KEY ("conceito_id") REFERENCES "conceito" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documento" ADD FOREIGN KEY ("dataset_id") REFERENCES "dataset" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documento_trecho" ADD FOREIGN KEY ("documento_id") REFERENCES "documento" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resposta_sistema" ADD FOREIGN KEY ("consulta_usuario_id") REFERENCES "consulta_usuario" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "consulta_usuario" ADD FOREIGN KEY ("chat_id") REFERENCES "chat" ("id") DEFERRABLE INITIALLY IMMEDIATE;
