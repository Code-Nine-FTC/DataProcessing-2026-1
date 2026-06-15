-- Seed de dados sintéticos para testes de integração
-- Geometrias simplificadas no estado de São Paulo (SRID 4326)

-- Extensoes
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Estado
INSERT INTO estado (id, sigla, nome, geom)
VALUES (35, 'SP', 'São Paulo',
  ST_GeomFromText('MULTIPOLYGON(((-53.0 -25.0, -44.0 -25.0, -44.0 -20.0, -53.0 -20.0, -53.0 -25.0)))', 4326));

-- Municipios
INSERT INTO municipio (id, codigo_ibge, nome, nome_normalizado, estado_id, geom)
VALUES
  (3548708, '3548708', 'São José dos Campos', 'sao jose dos campos', 35,
    ST_GeomFromText('MULTIPOLYGON(((-46.0 -23.3, -45.8 -23.3, -45.8 -23.1, -46.0 -23.1, -46.0 -23.3)))', 4326)),
  (3524402, '3524402', 'Jacareí', 'jacarei', 35,
    ST_GeomFromText('MULTIPOLYGON(((-46.1 -23.4, -45.9 -23.4, -45.9 -23.2, -46.1 -23.2, -46.1 -23.4)))', 4326)),
  (3518800, '3518800', 'Caçapava', 'cacapava', 35,
    ST_GeomFromText('MULTIPOLYGON(((-45.8 -23.2, -45.6 -23.2, -45.6 -23.0, -45.8 -23.0, -45.8 -23.2)))', 4326));

-- Fonte de Dados
INSERT INTO fonte_dado (id, nome, orgao_responsavel, url_origem, formato)
VALUES
  ('a0000000-0000-0000-0000-000000000001', 'INPE Queimadas', 'INPE', 'https://queimadas.dgi.inpe.br', 'API'),
  ('a0000000-0000-0000-0000-000000000002', 'SICAR', 'CAR', 'https://www.car.gov.br', 'API');

-- Imovel Rural
INSERT INTO imovel_rural (id, codigo_car, nome_imovel, municipio_id, area_ha, geom, centroid)
VALUES
  ('b0000000-0000-0000-0000-000000000001', 'SP-350000-000000000001', 'Fazenda Teste Alpha', 3548708, 120.50,
    ST_GeomFromText('MULTIPOLYGON(((-45.95 -23.22, -45.90 -23.22, -45.90 -23.18, -45.95 -23.18, -45.95 -23.22)))', 4326),
    ST_GeomFromText('POINT(-45.925 -23.20)', 4326)),
  ('b0000000-0000-0000-0000-000000000002', 'SP-350000-000000000002', 'Sitio Teste Beta', 3524402, 45.00,
    ST_GeomFromText('MULTIPOLYGON(((-46.05 -23.35, -46.00 -23.35, -46.00 -23.30, -46.05 -23.30, -46.05 -23.35)))', 4326),
    ST_GeomFromText('POINT(-46.025 -23.325)', 4326)),
  ('b0000000-0000-0000-0000-000000000003', 'SP-350000-000000000003', 'Fazenda Teste Gamma', 3518800, 200.00,
    ST_GeomFromText('MULTIPOLYGON(((-45.75 -23.15, -45.70 -23.15, -45.70 -23.10, -45.75 -23.10, -45.75 -23.15)))', 4326),
    ST_GeomFromText('POINT(-45.725 -23.125)', 4326));

-- Queimadas
INSERT INTO queimada_evento (id, municipio_id, data_ocorrencia, intensidade, risco_fogo, fonte_sensor, geom)
VALUES
  ('c0000000-0000-0000-0000-000000000001', 3548708, '2026-01-15', 0.85, 0.90, 'MODIS',
    ST_GeomFromText('POINT(-45.92 -23.20)', 4326)),
  ('c0000000-0000-0000-0000-000000000002', 3548708, '2026-01-20', 0.75, 0.80, 'MODIS',
    ST_GeomFromText('POINT(-45.93 -23.19)', 4326)),
  ('c0000000-0000-0000-0000-000000000003', 3524402, '2026-02-10', 0.60, 0.65, 'VIIRS',
    ST_GeomFromText('POINT(-46.03 -23.32)', 4326)),
  ('c0000000-0000-0000-0000-000000000004', 3524402, '2026-02-15', 0.55, 0.60, 'VIIRS',
    ST_GeomFromText('POINT(-46.02 -23.33)', 4326)),
  ('c0000000-0000-0000-0000-000000000005', 3518800, '2026-03-05', 0.90, 0.95, 'MODIS',
    ST_GeomFromText('POINT(-45.73 -23.12)', 4326));

-- Relacionamento Imovel-Queimada
INSERT INTO rel_imovel_queimada (imovel_rural_id, queimada_evento_id, distancia_m, dentro_imovel)
VALUES
  ('b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 1500.0, false),
  ('b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000002', 2000.0, false),
  ('b0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000003', 800.0, false),
  ('b0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004', 1200.0, false),
  ('b0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000005', 100.0, true);
