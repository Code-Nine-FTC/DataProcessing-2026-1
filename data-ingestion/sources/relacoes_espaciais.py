"""
Pós-processamento - Cálculo de Relacionamentos Espaciais

Esta não é uma pipeline ETL tradicional (Extract-Transform-Load).
Em vez disso, calcula interseções entre dados já carregados no banco de dados
usando PostGIS e cria registros em tabelas de relacionamento.

Tabelas afetadas:
  - rel_imovel_queimada
  - rel_imovel_desmatamento
  - rel_imovel_uc
  - rel_imovel_ti
  - rel_imovel_assentamento
  - rel_imovel_quilombo
  - rel_imovel_bacia

Executar APÓS todas as outras pipelines.
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import text

logger = logging.getLogger(__name__)


class SpatialRelationshipPostProcessor:
    """Calcula relacionamentos espaciais entre dados."""

    def __init__(self, engine):
        self.engine = engine

    def _calculate_relation(
        self,
        relation_table: str,
        source_table: str,
        source_id_col: str,
        target_table: str,
        target_id_col: str,
        relation_type: str = None,
    ) -> int:
        """
        Calcula relacionamentos espaciais genéricos.

        Args:
            relation_table: Tabela de relacionamento (ex: rel_imovel_uc)
            source_table: Tabela origem (ex: imovel_rural)
            source_id_col: Coluna ID na tabela origem
            target_table: Tabela alvo (ex: unidade_conservacao)
            target_id_col: Coluna ID na tabela alvo
            relation_type: Campo de tipo de relação (se aplicável)

        Returns:
            Número de relacionamentos criados
        """
        logger.info(f"Computing {source_table} ↔ {target_table} relationships...")

        with self.engine.begin() as conn:
            # Limpar relacionamentos antigos
            conn.execute(text(f"DELETE FROM {relation_table} WHERE TRUE"))
            conn.execute(text("SET LOCAL statement_timeout = '5min'"))

            # Índices espaciais para melhorar desempenho do ST_Intersects.
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS idx_{source_table}_geom_gist "
                f"ON {source_table} USING GIST (geom)"
            ))
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS idx_{target_table}_geom_gist "
                f"ON {target_table} USING GIST (geom)"
            ))

            # Inserir novos relacionamentos
            cols = [
                "id",
                f"{source_table.rstrip('s')}_id",
                f"{target_table.rstrip('s')}_id",
                "area_intersecao_ha",
                "percentual_sobreposicao",
            ]

            query = f"""
                INSERT INTO {relation_table}
                    ({', '.join(cols)})
                SELECT
                    gen_random_uuid(),
                    source.id,
                    target.id,
                    ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0
                        as area_intersecao_ha,
                    CASE
                        WHEN source.area_ha > 0 THEN
                            (ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0)
                            / source.area_ha * 100
                        ELSE 0
                    END as percentual_sobreposicao
                FROM {source_table} source
                JOIN {target_table} target
                  ON source.geom && target.geom
                 AND ST_Intersects(ST_MakeValid(source.geom), ST_MakeValid(target.geom))
            """

            conn.execute(text(query))
            result = conn.execute(text(f"SELECT COUNT(*) FROM {relation_table}"))
            count = result.scalar()

            logger.info(f"  → {count} relationships created")
            return count

    def calculate_imovel_queimada(self) -> int:
        """Calcula distância e continência: Imóvel ↔ Queimada (pontos)."""
        logger.info("Computing imovel_rural ↔ queimada_evento (points)...")

        try:
            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM rel_imovel_queimada WHERE TRUE"))
                conn.execute(text("SET LOCAL statement_timeout = '5min'"))

                # Índices espaciais para acelerar a junção por proximidade.
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_imovel_rural_geom_gist "
                    "ON imovel_rural USING GIST (geom)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_queimada_evento_geom_gist "
                    "ON queimada_evento USING GIST (geom)"
                ))

                # Aproximação em graus (~5km) para evitar dependência de geography/srid refs.
                dist_deg = 5000.0 / 111320.0

                query = text("""
                    INSERT INTO rel_imovel_queimada
                        (id, imovel_rural_id, queimada_evento_id, distancia_m,
                         dentro_imovel, data_calculo)
                    SELECT
                        gen_random_uuid(),
                        ir.id,
                        qe.id,
                        ST_Distance(ST_MakeValid(ir.geom), ST_MakeValid(qe.geom)) * 111320.0 as distancia_m,
                        ST_Contains(ST_MakeValid(ir.geom), ST_MakeValid(qe.geom)) as dentro_imovel,
                        :agora
                                        FROM queimada_evento qe
                                        JOIN imovel_rural ir
                                            ON ir.geom && ST_Expand(qe.geom, :dist_deg)
                                         AND ST_DWithin(ST_MakeValid(ir.geom), ST_MakeValid(qe.geom), :dist_deg)
                """)

                conn.execute(query, {"agora": datetime.now(), "dist_deg": dist_deg})
                result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_queimada"))
                count = result.scalar()
                logger.info(f"  → {count} relationships created")
                return count
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_queimada relationships: {str(e)}")
            return 0

    def calculate_imovel_desmatamento(self) -> int:
        """Calcula: Imóvel ↔ Desmatamento (polígonos)."""
        try:
            return self._calculate_relation(
                "rel_imovel_desmatamento",
                "imovel_rural",
                "id",
                "desmatamento_alerta",
                "id",
            )
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_desmatamento relationships: {str(e)}")
            return 0

    def calculate_imovel_uc(self) -> int:
        """Calcula: Imóvel ↔ Unidade de Conservação."""
        try:
            return self.calculate_imovel_uc_by_uc_batches()
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_uc relationships: {str(e)}")
            return 0

    def calculate_imovel_uc_batched(
        self,
        batch_size: int = 2000,
        max_batches: int | None = None,
        statement_timeout: str = "5min",
    ) -> int:
        """Calcula: Imóvel ↔ Unidade de Conservação em lotes para evitar timeout."""
        logger.info(
            "Computing imovel_rural ↔ unidade_conservacao relationships (batched, size=%s)...",
            batch_size,
        )

        last_id = "00000000-0000-0000-0000-000000000000"
        batches = 0

        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM rel_imovel_uc WHERE TRUE"))
            conn.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))

            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_imovel_rural_geom_gist "
                "ON imovel_rural USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_unidade_conservacao_geom_gist "
                "ON unidade_conservacao USING GIST (geom)"
            ))

            while True:
                if max_batches is not None and batches >= max_batches:
                    break

                batch_ids = conn.execute(text("""
                    SELECT id
                    FROM imovel_rural
                    WHERE id > :last_id
                    ORDER BY id
                    LIMIT :limit
                """), {"last_id": last_id, "limit": batch_size}).fetchall()

                if not batch_ids:
                    break

                last_id = batch_ids[-1][0]

                query = text("""
                    WITH batch AS (
                        SELECT id, geom, area_ha
                        FROM imovel_rural
                        WHERE id > :last_id
                        ORDER BY id
                        LIMIT :limit
                    )
                    INSERT INTO rel_imovel_uc
                        (id, imovel_rural_id, unidade_conservacao_id,
                         area_intersecao_ha, percentual_sobreposicao)
                    SELECT
                        gen_random_uuid(),
                        source.id,
                        target.id,
                        ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0
                            as area_intersecao_ha,
                        CASE
                            WHEN source.area_ha > 0 THEN
                                (ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0)
                                / source.area_ha * 100
                            ELSE 0
                        END as percentual_sobreposicao
                    FROM batch source
                    JOIN unidade_conservacao target
                      ON source.geom && target.geom
                     AND ST_Intersects(ST_MakeValid(source.geom), ST_MakeValid(target.geom))
                """)

                conn.execute(query, {"last_id": last_id, "limit": batch_size})
                batches += 1
                logger.info("  → batch %s processed (last_id=%s)", batches, last_id)

            result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_uc"))
            count = result.scalar()

        logger.info("  → %s relationships created (batched)", count)
        return count

    def calculate_imovel_uc_batched_tiles(
        self,
        tile_size_deg: float = 0.5,
        margin_deg: float = 0.05,
        max_tiles: int | None = None,
        statement_timeout: str = "5min",
    ) -> int:
        """Calcula: Imóvel ↔ Unidade de Conservação em lotes por tiles espaciais."""
        logger.info(
            "Computing imovel_rural ↔ unidade_conservacao relationships (tiles=%s, margin=%s)...",
            tile_size_deg,
            margin_deg,
        )

        with self.engine.begin() as conn:
            # Index creation can be slow; avoid timing out on DDL.
            conn.execute(text("SET LOCAL statement_timeout = '0'"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_imovel_rural_geom_gist "
                "ON imovel_rural USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_unidade_conservacao_geom_gist "
                "ON unidade_conservacao USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_rel_imovel_uc_pair "
                "ON rel_imovel_uc (imovel_rural_id, unidade_conservacao_id)"
            ))

            conn.execute(text("DELETE FROM rel_imovel_uc WHERE TRUE"))
            conn.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))

            bounds = conn.execute(text("""
                SELECT
                    ST_XMin(ext) AS minx,
                    ST_YMin(ext) AS miny,
                    ST_XMax(ext) AS maxx,
                    ST_YMax(ext) AS maxy
                FROM (SELECT ST_Extent(geom) AS ext FROM imovel_rural) s
            """)).fetchone()

            if not bounds or bounds[0] is None:
                logger.warning("No imovel_rural extent found for tiling.")
                return 0

            minx, miny, maxx, maxy = bounds
            tile_count = 0

            x = minx
            while x < maxx:
                y = miny
                while y < maxy:
                    if max_tiles is not None and tile_count >= max_tiles:
                        break

                    tile_minx = x
                    tile_miny = y
                    tile_maxx = min(x + tile_size_deg, maxx)
                    tile_maxy = min(y + tile_size_deg, maxy)

                    query = text("""
                        WITH tile AS (
                            SELECT ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326) AS geom
                        ),
                        tile_expanded AS (
                            SELECT ST_Expand(geom, :margin) AS geom FROM tile
                        )
                        INSERT INTO rel_imovel_uc
                            (id, imovel_rural_id, unidade_conservacao_id,
                             area_intersecao_ha, percentual_sobreposicao)
                        SELECT
                            gen_random_uuid(),
                            source.id,
                            target.id,
                            ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0
                                as area_intersecao_ha,
                            CASE
                                WHEN source.area_ha > 0 THEN
                                    (ST_Area(ST_Intersection(ST_MakeValid(source.geom), ST_MakeValid(target.geom))) / 10000.0)
                                    / source.area_ha * 100
                                ELSE 0
                            END as percentual_sobreposicao
                        FROM imovel_rural source
                        JOIN unidade_conservacao target
                          ON source.geom && target.geom
                         AND ST_Intersects(ST_MakeValid(source.geom), ST_MakeValid(target.geom))
                        WHERE source.geom && (SELECT geom FROM tile)
                          AND ST_Intersects(ST_MakeValid(source.geom), (SELECT geom FROM tile))
                          AND target.geom && (SELECT geom FROM tile_expanded)
                          AND ST_Intersects(ST_MakeValid(target.geom), (SELECT geom FROM tile_expanded))
                          AND NOT EXISTS (
                              SELECT 1 FROM rel_imovel_uc r
                              WHERE r.imovel_rural_id = source.id
                                AND r.unidade_conservacao_id = target.id
                          )
                    """)

                    conn.execute(query, {
                        "minx": tile_minx,
                        "miny": tile_miny,
                        "maxx": tile_maxx,
                        "maxy": tile_maxy,
                        "margin": margin_deg,
                    })

                    tile_count += 1
                    logger.info(
                        "  → tile %s processed (%.4f, %.4f, %.4f, %.4f)",
                        tile_count,
                        tile_minx,
                        tile_miny,
                        tile_maxx,
                        tile_maxy,
                    )

                    y += tile_size_deg
                if max_tiles is not None and tile_count >= max_tiles:
                    break
                x += tile_size_deg

            result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_uc"))
            count = result.scalar()

        logger.info("  → %s relationships created (tiles)", count)
        return count

    def calculate_imovel_uc_batched_tiles_optimized(
        self,
        tile_size_deg: float = 0.5,
        margin_deg: float = 0.05,
        max_tiles: int | None = None,
        statement_timeout: str = "10min",
        subdivide_max_vertices: int = 256,
    ) -> int:
        """Calcula: Imóvel ↔ Unidade de Conservação com tiles + subdivisão de UCs."""
        logger.info(
            "Computing imovel_rural ↔ unidade_conservacao relationships (tiles=%s, margin=%s, subdivide=%s)...",
            tile_size_deg,
            margin_deg,
            subdivide_max_vertices,
        )

        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM rel_imovel_uc WHERE TRUE"))
            conn.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))

            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_imovel_rural_geom_gist "
                "ON imovel_rural USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_unidade_conservacao_geom_gist "
                "ON unidade_conservacao USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_rel_imovel_uc_pair "
                "ON rel_imovel_uc (imovel_rural_id, unidade_conservacao_id)"
            ))

            # Subdivide UCs para acelerar o join espacial sem perda de precisão.
            conn.execute(text("DROP TABLE IF EXISTS tmp_uc_subdivided"))
            conn.execute(text("""
                CREATE TEMP TABLE tmp_uc_subdivided AS
                SELECT
                    uc.id AS uc_id,
                    (ST_Dump(ST_Subdivide(ST_MakeValid(uc.geom), :max_vertices))).geom AS geom
                FROM unidade_conservacao uc
            """), {"max_vertices": subdivide_max_vertices})
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_tmp_uc_subdivided_geom_gist "
                "ON tmp_uc_subdivided USING GIST (geom)"
            ))

            bounds = conn.execute(text("""
                SELECT
                    ST_XMin(ext) AS minx,
                    ST_YMin(ext) AS miny,
                    ST_XMax(ext) AS maxx,
                    ST_YMax(ext) AS maxy
                FROM (SELECT ST_Extent(geom) AS ext FROM imovel_rural) s
            """)).fetchone()

            if not bounds or bounds[0] is None:
                logger.warning("No imovel_rural extent found for tiling.")
                return 0

            minx, miny, maxx, maxy = bounds
            tile_count = 0

            x = minx
            while x < maxx:
                y = miny
                while y < maxy:
                    if max_tiles is not None and tile_count >= max_tiles:
                        break

                    tile_minx = x
                    tile_miny = y
                    tile_maxx = min(x + tile_size_deg, maxx)
                    tile_maxy = min(y + tile_size_deg, maxy)

                    query = text("""
                        WITH tile AS (
                            SELECT ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326) AS geom
                        ),
                        tile_expanded AS (
                            SELECT ST_Expand(geom, :margin) AS geom FROM tile
                        )
                        INSERT INTO rel_imovel_uc
                            (id, imovel_rural_id, unidade_conservacao_id,
                             area_intersecao_ha, percentual_sobreposicao)
                        SELECT
                            gen_random_uuid(),
                            source.id,
                            target.uc_id,
                            ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0
                                as area_intersecao_ha,
                            CASE
                                WHEN source.area_ha > 0 THEN
                                    (ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0)
                                    / source.area_ha * 100
                                ELSE 0
                            END as percentual_sobreposicao
                        FROM imovel_rural source
                        JOIN tmp_uc_subdivided target
                          ON source.geom && target.geom
                         AND ST_Intersects(source.geom, target.geom)
                        WHERE source.geom && (SELECT geom FROM tile)
                          AND ST_Intersects(source.geom, (SELECT geom FROM tile))
                          AND target.geom && (SELECT geom FROM tile_expanded)
                          AND ST_Intersects(target.geom, (SELECT geom FROM tile_expanded))
                          AND NOT EXISTS (
                              SELECT 1 FROM rel_imovel_uc r
                              WHERE r.imovel_rural_id = source.id
                                AND r.unidade_conservacao_id = target.uc_id
                          )
                    """)

                    conn.execute(query, {
                        "minx": tile_minx,
                        "miny": tile_miny,
                        "maxx": tile_maxx,
                        "maxy": tile_maxy,
                        "margin": margin_deg,
                    })

                    tile_count += 1
                    logger.info(
                        "  → tile %s processed (%.4f, %.4f, %.4f, %.4f)",
                        tile_count,
                        tile_minx,
                        tile_miny,
                        tile_maxx,
                        tile_maxy,
                    )

                    y += tile_size_deg
                if max_tiles is not None and tile_count >= max_tiles:
                    break
                x += tile_size_deg

            result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_uc"))
            count = result.scalar()

        logger.info("  → %s relationships created (tiles+subdivide)", count)
        return count

    def calculate_imovel_uc_by_uc_batches(
        self,
        batch_size: int = 10,
        statement_timeout: str = "5min",
    ) -> int:
        """Calcula: Imóvel ↔ Unidade de Conservação em lotes por UC."""
        logger.info(
            "Computing imovel_rural ↔ unidade_conservacao relationships (uc_batches=%s)...",
            batch_size,
        )

        total_inserted = 0

        with self.engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '0'"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_imovel_rural_geom_gist "
                "ON imovel_rural USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_unidade_conservacao_geom_gist "
                "ON unidade_conservacao USING GIST (geom)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_rel_imovel_uc_pair "
                "ON rel_imovel_uc (imovel_rural_id, unidade_conservacao_id)"
            ))

            conn.execute(text("DELETE FROM rel_imovel_uc WHERE TRUE"))

            uc_ids = [row[0] for row in conn.execute(
                text("SELECT id FROM unidade_conservacao ORDER BY id")
            ).fetchall()]

            if not uc_ids:
                logger.warning("No unidade_conservacao records found.")
                return 0

            for i in range(0, len(uc_ids), batch_size):
                batch = uc_ids[i:i + batch_size]
                conn.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))

                query = text("""
                    INSERT INTO rel_imovel_uc
                        (id, imovel_rural_id, unidade_conservacao_id,
                         area_intersecao_ha, percentual_sobreposicao)
                    SELECT
                        gen_random_uuid(),
                        source.id,
                        target.id,
                        ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0
                            as area_intersecao_ha,
                        CASE
                            WHEN source.area_ha > 0 THEN
                                (ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0)
                                / source.area_ha * 100
                            ELSE 0
                        END as percentual_sobreposicao
                    FROM unidade_conservacao target
                    JOIN imovel_rural source
                      ON source.geom && target.geom
                     AND ST_Intersects(source.geom, target.geom)
                    WHERE target.id = ANY(:uc_ids)
                """)

                conn.execute(query, {"uc_ids": batch})
                batch_count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM rel_imovel_uc WHERE unidade_conservacao_id = ANY(:uc_ids)"
                    ),
                    {"uc_ids": batch},
                ).scalar()

                total_inserted += int(batch_count or 0)
                logger.info(
                    "  → batch %s/%s processed (ucs=%s, inserted=%s)",
                    (i // batch_size) + 1,
                    (len(uc_ids) + batch_size - 1) // batch_size,
                    len(batch),
                    batch_count,
                )

            result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_uc"))
            count = result.scalar()

        logger.info("  → %s relationships created (uc batches)", count)
        return int(count or 0)

    def calculate_imovel_ti(self) -> int:
        """Calcula: Imóvel ↔ Terra Indígena."""
        try:
            return self._calculate_relation(
                "rel_imovel_ti",
                "imovel_rural",
                "id",
                "terra_indigena",
                "id",
            )
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_ti relationships: {str(e)}")
            return 0

    def calculate_imovel_assentamento(self) -> int:
        """Calcula: Imóvel ↔ Assentamento Rural."""
        try:
            return self._calculate_relation(
                "rel_imovel_assentamento",
                "imovel_rural",
                "id",
                "assentamento_rural",
                "id",
            )
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_assentamento relationships: {str(e)}")
            return 0

    def calculate_imovel_quilombo(self) -> int:
        """Calcula: Imóvel ↔ Território Quilombola."""
        try:
            return self._calculate_relation(
                "rel_imovel_quilombo",
                "imovel_rural",
                "id",
                "territorio_quilombola",
                "id",
            )
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_quilombo relationships: {str(e)}")
            return 0

    def populate_documentos_from_datasets(self) -> int:
        """Sincroniza metadados dos Datasets para a tabela documento e documento_trecho."""
        logger.info("Computing fallback: dataset -> documento_trecho (embeddings)...")
        
        try:
            # Requer import do embedder do pipeline NLP
            import sys
            import os
            # Adiciona a raiz do projeto no sys.path se não estiver
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
            if base_dir not in sys.path:
                sys.path.append(base_dir)
                
            from nlp_processor.pipeline.embedder import get_embedder
            embedder = get_embedder()
            
            with self.engine.begin() as conn:
                # 1. Obter todos os datasets que ainda não viraram documento
                query_datasets = text("""
                    SELECT 
                        d.id as dataset_id, 
                        d.nome as dataset_nome, 
                        d.descricao, 
                        f.nome as fonte_nome, 
                        f.orgao_responsavel
                    FROM dataset d
                    JOIN fonte_dado f ON d.fonte_dado_id = f.id
                    WHERE d.id NOT IN (SELECT dataset_id FROM documento WHERE dataset_id IS NOT NULL)
                """)
                
                datasets = conn.execute(query_datasets).fetchall()
                if not datasets:
                    return 0
                
                count = 0
                for row in datasets:
                    doc_id = str(uuid.uuid4())
                    titulo = f"{row.fonte_nome} - {row.dataset_nome}"
                    texto_integral = (
                        f"Dataset: {row.dataset_nome}. "
                        f"Fonte de Dados: {row.fonte_nome} ({row.orgao_responsavel}). "
                        f"Descrição: {row.descricao or 'Não disponível'}."
                    )
                    
                    # 2. Inserir Documento
                    insert_doc = text("""
                        INSERT INTO documento (id, dataset_id, titulo, tipo, data_criacao, texto_integral)
                        VALUES (:id, :dataset_id, :titulo, 'metadata_dataset', :agora, :texto_integral)
                    """)
                    conn.execute(insert_doc, {
                        "id": doc_id, 
                        "dataset_id": row.dataset_id,
                        "titulo": titulo,
                        "agora": datetime.now(),
                        "texto_integral": texto_integral
                    })
                    
                    # 3. Gerar embedding e Inserir Documento Trecho
                    vector_embedding = embedder.embed(texto_integral)
                    embedding_str = f"[{','.join(str(f) for f in vector_embedding)}]"
                    tokens_count = len(texto_integral.split())
                    
                    insert_trecho = text("""
                        INSERT INTO documento_trecho (id, documento_id, texto, ordem, embedding, tokens_count)
                        VALUES (:id, :documento_id, :texto, 1, CAST(:embedding AS vector), :tokens)
                    """)
                    conn.execute(insert_trecho, {
                        "id": str(uuid.uuid4()),
                        "documento_id": doc_id,
                        "texto": texto_integral,
                        "embedding": embedding_str,
                        "tokens": tokens_count
                    })
                    
                    count += 1
                
                logger.info(f"  → {count} documents and embeddings created")
                return count
                
        except Exception as e:
            logger.warning(f"Failed to populate documents and embeddings: {str(e)}")
            return 0

    def calculate_imovel_bacia(self) -> int:
        """Calcula: Imóvel ↔ Bacia Hidrográfica."""
        logger.info("Computing imovel_rural ↔ bacia_hidrografica relationships...")

        try:
            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM rel_imovel_bacia WHERE TRUE"))

                query = text("""
                    INSERT INTO rel_imovel_bacia
                        (id, imovel_rural_id, bacia_hidrografica_id,
                         area_intersecao_ha, percentual_sobreposicao)
                    SELECT
                        gen_random_uuid(),
                        ir.id,
                        bh.id,
                        ST_Area(ST_Intersection(ST_MakeValid(ir.geom), ST_MakeValid(bh.geom))) / 10000.0 as area_intersecao_ha,
                        CASE
                            WHEN ir.area_ha > 0 THEN
                                (ST_Area(ST_Intersection(ST_MakeValid(ir.geom), ST_MakeValid(bh.geom))) / 10000.0)
                                / ir.area_ha * 100
                            ELSE 0
                        END as percentual_sobreposicao
                    FROM imovel_rural ir
                    JOIN bacia_hidrografica bh ON ST_Intersects(ST_MakeValid(ir.geom), ST_MakeValid(bh.geom))
                    WHERE NOT EXISTS (
                        SELECT 1 FROM rel_imovel_bacia
                        WHERE imovel_rural_id = ir.id
                          AND bacia_hidrografica_id = bh.id
                    )
                """)

                conn.execute(query)
                result = conn.execute(text("SELECT COUNT(*) FROM rel_imovel_bacia"))
                count = result.scalar()
                logger.info(f"  → {count} relationships created")
                return count
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_bacia relationships: {str(e)}")
            return 0

    def link_camada_estadual_to_municipios(self) -> int:
        """Relaciona camada_estadual_ambiental ao município mais aderente espacialmente.

        Regra principal: município com maior área de interseção.
        Fallback: município que contém um ponto interno da geometria.
        """
        logger.info("Linking camada_estadual_ambiental → municipio...")

        try:
            with self.engine.begin() as conn:
                updated_total = 0
                # Escolhe um único município por ativo com base na maior interseção.
                r1 = conn.execute(text("""
                    WITH ranked AS (
                        SELECT
                            cea.id AS camada_id,
                            m.id AS municipio_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY cea.id
                                ORDER BY ST_Area(ST_Intersection(ST_MakeValid(cea.geom), m.geom)) DESC,
                                         m.id
                            ) AS rn
                        FROM camada_estadual_ambiental cea
                        JOIN municipio m ON ST_Intersects(ST_MakeValid(cea.geom), m.geom)
                        WHERE cea.municipio_id IS NULL
                    )
                    UPDATE camada_estadual_ambiental cea
                    SET municipio_id = ranked.municipio_id
                    FROM ranked
                    WHERE cea.id = ranked.camada_id
                      AND ranked.rn = 1
                    RETURNING cea.id
                """))
                updated_total += len(r1.fetchall())

                # Fallback para geometrias que não intersectaram por ruído topológico.
                r2 = conn.execute(text("""
                                        UPDATE camada_estadual_ambiental cea
                                        SET municipio_id = m.id
                                        FROM municipio m
                                        WHERE cea.municipio_id IS NULL
                                            AND ST_Contains(m.geom, ST_PointOnSurface(ST_MakeValid(cea.geom)))
                                        RETURNING cea.id
                """))
                updated_total += len(r2.fetchall())

                # Último fallback: município mais próximo do ponto interno da geometria.
                r3 = conn.execute(text("""
                    WITH nearest AS (
                        SELECT
                            cea.id AS camada_id,
                            m.id AS municipio_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY cea.id
                                ORDER BY ST_Distance(
                                    ST_PointOnSurface(ST_MakeValid(cea.geom)),
                                    ST_PointOnSurface(m.geom)
                                ) ASC,
                                m.id
                            ) AS rn
                        FROM camada_estadual_ambiental cea
                        JOIN municipio m ON TRUE
                        WHERE cea.municipio_id IS NULL
                    )
                    UPDATE camada_estadual_ambiental cea
                    SET municipio_id = nearest.municipio_id
                    FROM nearest
                    WHERE cea.id = nearest.camada_id
                      AND nearest.rn = 1
                    RETURNING cea.id
                """))
                updated_total += len(r3.fetchall())

            logger.info("  → %s registros de camada_estadual_ambiental vinculados a município", updated_total)
            return updated_total
        except Exception as e:
            logger.warning("Failed to link camada_estadual_ambiental to municipio: %s", str(e))
            return 0

    def run_all(self):
        """Executa todos os cálculos de relacionamentos."""
        logger.info("\n" + "="*70)
        logger.info("SPATIAL RELATIONSHIP POST-PROCESSING")
        logger.info("="*70 + "\n")

        try:
            from sources.inpe import link_queimadas_to_municipios
            link_queimadas_to_municipios(self.engine)
        except Exception as e:
            logger.warning(
                "Não foi possível atualizar municipio_id em queimada_evento: %s", e
            )

        camada_municipio_updates = self.link_camada_estadual_to_municipios()

        with self.engine.connect() as conn:
            n_im = conn.execute(
                text("SELECT COUNT(*) FROM imovel_rural")
            ).scalar()
        if not n_im:
            logger.warning(
                "Tabela imovel_rural está vazia: as tabelas rel_imovel_* dependem de "
                "imóveis carregados (ex.: pipeline car). Ordem sugerida: car → demais fontes → main.py (padrão + car)."
            )

        results = {
            "queimada": self.calculate_imovel_queimada(),
            "desmatamento": self.calculate_imovel_desmatamento(),
            "uc": self.calculate_imovel_uc(),
            "ti": self.calculate_imovel_ti(),
            "assentamento": self.calculate_imovel_assentamento(),
            "quilombo": self.calculate_imovel_quilombo(),
            "bacia": self.calculate_imovel_bacia(),
            "documentos_fallback": self.populate_documentos_from_datasets(),
        }

        logger.info("\n" + "="*70)
        logger.info("SUMMARY")
        logger.info("="*70)
        total = sum(results.values())
        logger.info(
            "  %-20s → %6s updates",
            "camada->municipio",
            camada_municipio_updates,
        )
        for name, count in results.items():
            logger.info(f"  {name:20} → {count:6} relationships")
        logger.info(f"  {'TOTAL':20} → {total:6} relationships")
        logger.info("="*70 + "\n")

        return results


def run_post_processing(engine):
    """Entry point para pós-processamento."""
    processor = SpatialRelationshipPostProcessor(engine)
    processor.run_all()
