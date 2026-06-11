# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum


class Dominio(str, Enum):
    QUEIMADA = "queimada"
    DESMATAMENTO = "desmatamento"
    UNIDADE_CONSERVACAO = "unidade_conservacao"
    TERRA_INDIGENA = "terra_indigena"
    QUILOMBOLA = "quilombola"
    ASSENTAMENTO = "assentamento"
    IMOVEL_RURAL = "imovel_rural"
    CAMADA_ESTADUAL = "camada_estadual"
    DOCUMENTO = "documento"


class Operacao(str, Enum):
    LISTAR = "listar"
    RANKEAR = "rankear"
    SOBREPOR = "sobrepor"
    PASSIVOS = "passivos"
