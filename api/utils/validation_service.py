import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

async def validate_database_crs_integrity(db: AsyncSession, auto_correct: bool = False) -> bool:
    """
    Executa a auditoria das geometrias para validar se todas as tabelas espaciais obedecem às regras 
    do SRID nativo (4326) e as premissas matemáticas de topologia usando PostGIS.
    Se auto_correct for True, tenta corrigir geometrias inválidas com ST_MakeValid e ST_CollectionExtract.
    """
    is_fully_healthy = True
    
    try:
        # Busca todas as tabelas e colunas com geometria (ignorando views e esquemas de sistema)
        tables_query = text("""
            SELECT f_table_name, f_geometry_column 
            FROM geometry_columns 
            WHERE f_table_schema = 'public';
        """)
        tables_result = await db.execute(tables_query)
        spatial_tables = tables_result.fetchall()

        for table_name, geom_col in spatial_tables:
            # 1. Varredura por inconsistência no SRID.
            srid_query = text(f"""
                SELECT id, ST_SRID({geom_col}) AS current_srid 
                FROM {table_name} 
                WHERE ST_SRID({geom_col}) != 4326 AND {geom_col} IS NOT NULL;
            """)
            srid_result = await db.execute(srid_query)
            inconsistent_srid_records = srid_result.fetchall()
            
            if inconsistent_srid_records:
                is_fully_healthy = False
                for record in inconsistent_srid_records:
                    logger.error(f"[Integrity ERROR] Tabela '{table_name}': Registro ID {record.id} possui CRS atípico EPSG:{record.current_srid}.")
            
            # 2. Varredura de Topologia
            topologic_query = text(f"""
                SELECT id, ST_IsValidReason({geom_col}) AS invalidity_reason 
                FROM {table_name} 
                WHERE {geom_col} IS NOT NULL AND ST_IsValid({geom_col}) = false;
            """)
            topologic_result = await db.execute(topologic_query)
            invalid_geom_records = topologic_result.fetchall()

            if invalid_geom_records:
                is_fully_healthy = False
                for record in invalid_geom_records:
                    logger.error(f"[Topology ERROR] Tabela '{table_name}': Geometria corrompida para ID {record.id}. Motivo: {record.invalidity_reason}")
                
                # Opcional: tentar corrigir as geometrias defeituosas.
                # ST_CollectionExtract(geom, 3) preserva apenas os polígonos dentro de uma GeometryCollection.
                if auto_correct:
                    logger.warning(f"[Autocorrect] Iniciando correção em '{table_name}'...")
                    fix_query = text(f"""
                        UPDATE {table_name}
                        SET {geom_col} = ST_Multi(ST_CollectionExtract(ST_MakeValid({geom_col}), 3))
                        WHERE ST_IsValid({geom_col}) = false AND {geom_col} IS NOT NULL;
                    """)
                    await db.execute(fix_query)
                    await db.commit()
                    logger.info(f"[Autocorrect OK] Tabela '{table_name}' corrigida com ST_MakeValid.")
            
        if is_fully_healthy:
            logger.info("[Topology & Integrity OK] Todas as tabelas estão consistentes em EPSG:4326 e topologicamente saudáveis.")

        return is_fully_healthy

    except SQLAlchemyError as err:
        await db.rollback()
        logger.error(f"Erro crítico validando/corrigindo conformidades espaciais: {err}")
        return False