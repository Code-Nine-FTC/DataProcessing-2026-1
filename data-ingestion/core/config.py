"""
Configuração centralizada da aplicação.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Configuração do banco de dados."""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @staticmethod
    def from_env() -> "DatabaseConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://localhost/data_processing"
        )
        return DatabaseConfig(
            url=url,
            pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )


@dataclass
class WFSConfig:
    """Configuração de requisições WFS."""
    timeout: int = 120
    batch_size: int = 500
    max_retries: int = 3
    retry_delay: int = 5

    @staticmethod
    def from_env() -> "WFSConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return WFSConfig(
            timeout=int(os.getenv("WFS_TIMEOUT", 120)),
            batch_size=int(os.getenv("WFS_BATCH_SIZE", 500)),
            max_retries=int(os.getenv("WFS_MAX_RETRIES", 3)),
            retry_delay=int(os.getenv("WFS_RETRY_DELAY", 5)),
        )


@dataclass
class AppConfig:
    """Configuração central da aplicação."""
    db: DatabaseConfig
    wfs: WFSConfig
    debug: bool = False
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> "AppConfig":
        """Cria configuração completa a partir de variáveis de ambiente."""
        return AppConfig(
            db=DatabaseConfig.from_env(),
            wfs=WFSConfig.from_env(),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
