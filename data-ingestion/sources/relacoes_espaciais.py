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
        logger.info(
            f"Computing {source_table} ↔ {target_table} relationships..."
        )

        with self.engine.begin() as conn:
            # Limpar relacionamentos antigos
            conn.execute(text(f"DELETE FROM {relation_table} WHERE TRUE"))

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
                    ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0
                        as area_intersecao_ha,
                    CASE
                        WHEN source.area_ha > 0 THEN
                            (ST_Area(ST_Intersection(source.geom, target.geom)) / 10000.0)
                            / source.area_ha * 100
                        ELSE 0
                    END as percentual_sobreposicao
                FROM {source_table} source
                JOIN {target_table} target ON ST_Intersects(source.geom, target.geom)
                WHERE NOT EXISTS (
                    SELECT 1 FROM {relation_table} rel
                    WHERE rel.{source_table.rstrip('s')}_id = source.id
                      AND rel.{target_table.rstrip('s')}_id = target.id
                )
            """

            result = conn.execute(text(query))
            count = result.rowcount
            logger.info(f"  → {count} relationships created")
            return count

    def calculate_imovel_queimada(self) -> int:
        """Calcula distância e continência: Imóvel ↔ Queimada (pontos)."""
        logger.info("Computing imovel_rural ↔ queimada_evento (points)...")

        try:
            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM rel_imovel_queimada WHERE TRUE"))

                query = text("""
                    INSERT INTO rel_imovel_queimada
                        (id, imovel_rural_id, queimada_evento_id, distancia_m,
                         dentro_imovel, data_calculo)
                    SELECT
                        gen_random_uuid(),
                        ir.id,
                        qe.id,
                        ST_Distance(ir.geom::geography, qe.geom::geography) as distancia_m,
                        ST_Contains(ir.geom, qe.geom) as dentro_imovel,
                        :agora
                    FROM imovel_rural ir
                    CROSS JOIN queimada_evento qe
                    WHERE ST_DWithin(ir.geom::geography, qe.geom::geography, 5000)
                      AND NOT EXISTS (
                        SELECT 1 FROM rel_imovel_queimada
                        WHERE imovel_rural_id = ir.id
                          AND queimada_evento_id = qe.id
                      )
                """)

                conn.execute(query, {"agora": datetime.now()})
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
            return self._calculate_relation(
                "rel_imovel_uc",
                "imovel_rural",
                "id",
                "unidade_conservacao",
                "id",
            )
        except Exception as e:
            logger.warning(f"Failed to calculate imovel_uc relationships: {str(e)}")
            return 0

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
                        ST_Area(ST_Intersection(ir.geom, bh.geom)) / 10000.0 as area_intersecao_ha,
                        CASE
                            WHEN ir.area_ha > 0 THEN
                                (ST_Area(ST_Intersection(ir.geom, bh.geom)) / 10000.0)
                                / ir.area_ha * 100
                            ELSE 0
                        END as percentual_sobreposicao
                    FROM imovel_rural ir
                    JOIN bacia_hidrografica bh ON ST_Intersects(ir.geom, bh.geom)
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
        }

        logger.info("\n" + "="*70)
        logger.info("SUMMARY")
        logger.info("="*70)
        total = sum(results.values())
        for name, count in results.items():
            logger.info(f"  {name:20} → {count:6} relationships")
        logger.info(f"  {'TOTAL':20} → {total:6} relationships")
        logger.info("="*70 + "\n")

        return results


def run_post_processing(engine):
    """Entry point para pós-processamento."""
    processor = SpatialRelationshipPostProcessor(engine)
    processor.run_all()
