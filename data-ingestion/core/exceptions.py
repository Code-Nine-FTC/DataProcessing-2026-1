"""
Exceções customizadas da aplicação.
"""


class PipelineException(Exception):
    """Exceção base da pipeline."""
    pass


class ExtractionException(PipelineException):
    """Erro ao extrair dados da fonte."""
    pass


class TransformationException(PipelineException):
    """Erro ao transformar dados."""
    pass


class LoadException(PipelineException):
    """Erro ao carregar dados no banco."""
    pass


class ValidationException(PipelineException):
    """Erro ao validar dados."""
    pass


class ConfigException(PipelineException):
    """Erro de configuração."""
    pass


class DataSourceException(PipelineException):
    """Erro ao acessar fonte de dados."""
    pass
