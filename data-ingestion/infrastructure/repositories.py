"""
Repositórios - Abstração para acesso aos dados no banco.
"""
import uuid
import logging
from datetime import datetime, date
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.exceptions import LoadException
from domain.entities import FonteDado, Dataset

logger = logging.getLogger(__name__)


class FonteDadoRepository:
    """Repositório para gerenciar FonteDado."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def find_by_name(self, nome: str) -> Optional[str]:
        """Busca FonteDado pelo nome e retorna seu UUID."""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("SELECT id FROM fonte_dado WHERE nome = :nome"),
                    {"nome": nome},
                ).fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            raise LoadException(f"Failed to find FonteDado: {str(e)}")

    def create(self, fonte: FonteDado) -> str:
        """Cria uma nova FonteDado se não existir."""
        existing_id = self.find_by_name(fonte.nome)
        if existing_id:
            logger.info(f"FonteDado '{fonte.nome}' already exists: {existing_id}")
            return existing_id

        fonte_id = str(uuid.uuid4())
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO fonte_dado
                            (id, nome, orgao_responsavel, url_origem, formato,
                             periodicidade, escopo_geografico, licenca, ativo)
                        VALUES
                            (:id, :nome, :orgao, :url, :fmt, :period, :escopo, :licenca, true)
                    """),
                    {
                        "id": fonte_id,
                        "nome": fonte.nome,
                        "orgao": fonte.orgao_responsavel,
                        "url": fonte.url_origem,
                        "fmt": fonte.formato,
                        "period": fonte.periodicidade,
                        "escopo": fonte.escopo_geografico,
                        "licenca": fonte.licenca,
                    },
                )
            logger.info(f"Created FonteDado: {fonte.nome} ({fonte_id})")
            return fonte_id
        except Exception as e:
            raise LoadException(f"Failed to create FonteDado: {str(e)}")


class DatasetRepository:
    """Repositório para gerenciar Dataset."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def find_by_fonte_and_name(self, fonte_id: str, nome: str) -> Optional[str]:
        """Busca Dataset pelo FonteDado e nome."""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT id FROM dataset
                        WHERE fonte_dado_id = :fid AND nome = :nome
                    """),
                    {"fid": fonte_id, "nome": nome},
                ).fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            raise LoadException(f"Failed to find Dataset: {str(e)}")

    def create(
        self,
        fonte_id: str,
        nome: str,
        descricao: Optional[str] = None,
        versao: Optional[str] = None,
        data_referencia: Optional[date] = None,
    ) -> Tuple[str, bool]:
        """
        Cria um novo Dataset se não existir.

        Returns:
            Tupla (dataset_id, is_new)
        """
        existing_id = self.find_by_fonte_and_name(fonte_id, nome)
        if existing_id:
            logger.info(f"Dataset '{nome}' already exists: {existing_id}")
            return existing_id, False

        dataset_id = str(uuid.uuid4())
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO dataset
                            (id, fonte_dado_id, nome, descricao, versao,
                             data_coleta, data_referencia)
                        VALUES
                            (:id, :fid, :nome, :descricao, :version,
                             :coleta, :referencia)
                    """),
                    {
                        "id": dataset_id,
                        "fid": fonte_id,
                        "nome": nome,
                        "descricao": descricao,
                        "version": versao,
                        "coleta": datetime.now(),
                        "referencia": data_referencia,
                    },
                )
            logger.info(f"Created Dataset: {nome} ({dataset_id})")
            return dataset_id, True
        except Exception as e:
            raise LoadException(f"Failed to create Dataset: {str(e)}")


class MunicipioRepository:
    """Repositório para buscar municípios por nome e UF."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def find_by_name_and_state(self, municipio_nome: str, uf: str, geom_wkt: Optional[str] = None) -> Optional[int]:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT m.id 
                        FROM municipio m
                        JOIN estado e ON m.estado_id = e.id
                        WHERE unaccent(LOWER(m.nome)) = unaccent(LOWER(:mun_nome)) 
                        AND UPPER(e.sigla) = UPPER(:uf)

                        UNION ALL

                        -- Só executa esta parte se a primeira não retornar nada (LIMIT 1 no final do bloco todo)
                        SELECT m.id 
                        FROM municipio m
                        WHERE ST_Within(ST_Centroid(ST_SetSRID(ST_GeomFromEWKT(:geom_wkt), 4326)), m.geom)

                        LIMIT 1
                    """),
                    {"mun_nome": municipio_nome, "uf": uf, "geom_wkt": geom_wkt},
                ).fetchone()
                return result[0] if result else None
        except Exception as e:
            raise LoadException(f"Failed to find Municipio: {str(e)}")
