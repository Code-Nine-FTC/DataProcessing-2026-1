# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    rotulo: str
    query_spec: dict
    sementes: tuple[str, ...]


@dataclass(frozen=True)
class GrupoSemantico:
    nome: str
    categorias: tuple[Categoria, ...]
    limiar: float


QUEIMADA = GrupoSemantico("queimada", limiar=0.70, categorias=(
    Categoria("listar", {"dominio": "queimada", "operacao": "listar"}, (
        "focos de queimada",
        "incêndio florestal",
        "fogo registrado",
        "foco de calor",
        "queimada detectada",
        "queimadas em área",
    )),
    Categoria("rankear", {"dominio": "queimada", "operacao": "rankear", "tema_ranking": "queimadas"}, (
        "municípios com mais queimadas",
        "ranking de focos de incêndio",
        "quais cidades tiveram mais fogo",
    )),
))

DESMATAMENTO = GrupoSemantico("desmatamento", limiar=0.70, categorias=(
    Categoria("listar", {"dominio": "desmatamento", "operacao": "listar"}, (
        "alertas de desmatamento detectados",
        "corte raso de floresta por desmatamento",
        "alerta PRODES de desmatamento",
        "alerta DETER de desmatamento",
        "desmatamento detectado",
    )),
    Categoria("rankear", {"dominio": "desmatamento", "operacao": "rankear", "tema_ranking": "desmatamentos"}, (
        "cidades com mais alertas de desmatamento",
        "ranking de áreas desmatadas por município",
        "qual município teve mais desmatamento",
    )),
))

TERRA_INDIGENA = GrupoSemantico("terra_indigena", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "terra_indigena", "operacao": "listar"}, (
        "terras indígenas",
        "área de demarcação indígena",
        "reserva indígena",
        "território indígena demarcado",
    )),
    Categoria("rankear", {"dominio": "terra_indigena", "operacao": "rankear", "tema_ranking": "terras_indigenas"}, (
        "municípios com mais terras indígenas",
        "ranking de terras indígenas por município",
        "qual cidade tem mais território indígena",
    )),
))

UNIDADE_CONSERVACAO = GrupoSemantico("unidade_conservacao", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "unidade_conservacao", "operacao": "listar"}, (
        "unidades de conservação",
        "parque nacional estadual",
        "área de proteção ambiental",
        "reserva extrativista",
    )),
    Categoria("rankear", {"dominio": "unidade_conservacao", "operacao": "rankear", "tema_ranking": "unidades_conservacao"}, (
        "municípios com mais unidades de conservação",
        "ranking de unidades de conservação por município",
        "qual cidade tem mais áreas de proteção",
    )),
))

QUILOMBOLA = GrupoSemantico("quilombola", limiar=0.78, categorias=(
    Categoria("listar", {"dominio": "quilombola", "operacao": "listar"}, (
        "territórios quilombolas",
        "comunidades quilombolas",
        "áreas quilombolas",
    )),
    Categoria("rankear", {"dominio": "quilombola", "operacao": "rankear", "tema_ranking": "quilombolas"}, (
        "municípios com mais territórios quilombolas",
        "ranking de quilombos por município",
        "qual cidade tem mais comunidades quilombolas",
    )),
))

ASSENTAMENTO = GrupoSemantico("assentamento", limiar=0.84, categorias=(
    Categoria("listar", {"dominio": "assentamento", "operacao": "listar"}, (
        "assentamentos rurais",
        "projetos de assentamento do INCRA",
        "áreas de reforma agrária",
        "assentamentos do ITESP",
    )),
))

IMOVEL_RURAL = GrupoSemantico("imovel_rural", limiar=0.80, categorias=(
    Categoria("listar", {"dominio": "imovel_rural", "operacao": "listar"}, (
        "imóveis rurais",
        "fazenda cadastrada no CAR",
        "propriedade rural",
        "código CAR",
    )),
    Categoria("passivos", {"dominio": "imovel_rural", "operacao": "passivos"}, (
        "passivos ambientais do imóvel rural",
        "imóvel com passivos ambientais",
        "sobreposição da propriedade rural com áreas protegidas",
        "infrações ambientais do imóvel rural",
        "débito ambiental da propriedade rural",
    )),
))

DOCUMENTO = GrupoSemantico("documento", limiar=0.85, categorias=(
    Categoria("buscar", {"dominio": "documento", "operacao": "listar"}, (
        "legislação ambiental",
        "como funciona o licenciamento",
        "regulamentação sobre desmatamento",
        "lei do Código Florestal",
        "normativa CONAMA",
    )),
))

CONTEXTO_ESPACIAL = GrupoSemantico("contexto_espacial", limiar=0.70, categorias=(
    Categoria("terra_indigena", {"contexto_espacial": {"dentro_de": "terra_indigena"}}, (
        "dentro de terras indígenas",
        "que intersectam territórios indígenas",
        "sobrepostos a terras indígenas demarcadas",
    )),
    Categoria("unidade_conservacao", {"contexto_espacial": {"dentro_de": "unidade_conservacao"}}, (
        "dentro de unidades de conservação",
        "em parques e reservas protegidas",
        "sobrepostos a áreas de proteção ambiental",
    )),
    Categoria("quilombola", {"contexto_espacial": {"dentro_de": "quilombola"}}, (
        "em territórios quilombolas",
        "dentro de áreas quilombolas",
        "sobrepostos a comunidades quilombolas",
    )),
    Categoria("assentamento", {"contexto_espacial": {"dentro_de": "assentamento"}}, (
        "dentro de assentamentos rurais",
        "em projetos de reforma agrária",
        "sobrepostos a assentamentos do INCRA",
    )),
))

OPERACAO_ESPECIAL = GrupoSemantico("operacao_especial", limiar=0.82, categorias=(
    Categoria("sobrepor", {"operacao": "sobrepor"}, (
        "sobreposição entre áreas",
        "intersecção de camadas territoriais",
        "cruzamento entre UC e TI",
    )),
    Categoria("rankear_geral", {"operacao": "rankear", "dominio": None}, (
        "quais municípios têm mais",
        "ranking geral de municípios",
        "maior concentração de dados ambientais",
    )),
))

GRUPOS: tuple[GrupoSemantico, ...] = (
    QUEIMADA,
    DESMATAMENTO,
    TERRA_INDIGENA,
    UNIDADE_CONSERVACAO,
    QUILOMBOLA,
    ASSENTAMENTO,
    IMOVEL_RURAL,
    DOCUMENTO,
    CONTEXTO_ESPACIAL,
    OPERACAO_ESPECIAL,
)
