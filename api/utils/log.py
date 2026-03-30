# -*- coding: utf-8 -*-
import logging
import sys
from .common import Singleton
from config import settings
import sys as _sys


class Log(metaclass= Singleton):
    def __init__(self) -> None:
        self._logger = logging.getLogger(settings.PROJECT_NAME)
        if not self._logger.handlers:
            self._project_name = settings.PROJECT_NAME
            self._log_level = settings.LOG_LEVEL
            self._configure_logger()

    def _configure_logger(self) -> None:
        self._logger = logging.getLogger(self._project_name)
        self._logger.setLevel(self._log_level)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

    def info(self, msg: str): self._logger.info(msg)
    def debug(self, msg: str): self._logger.debug(msg)
    def warning(self, msg: str): self._logger.warning(msg)
    
    def error(self, msg: str, exc_info: bool = True):
        ex_type, _, _ = _sys.exc_info()
        prefix = f"[{ex_type.__name__}] " if ex_type else ""
        self._logger.error(f"{prefix}{msg}", exc_info=exc_info)

    def critical(self, msg: str): self._logger.critical(msg)
    
        