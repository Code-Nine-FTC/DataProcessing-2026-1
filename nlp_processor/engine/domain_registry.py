# -*- coding: utf-8 -*-
from __future__ import annotations

from models.db_model import (
    AssentamentoRural,
    CamadaEstadualAmbiental,
    DesmatamentoAlerta,
    ImovelRural,
    QueimadaEvento,
    TerritorioQuilombola,
    TerraIndigena,
    UnidadeConservacao,
)
from nlp_processor.domain.enums import Dominio
from nlp_processor.engine.domain_spec import DomainSpec

REGISTRY: dict[Dominio, DomainSpec] = {
    Dominio.QUEIMADA: DomainSpec(
        model=QueimadaEvento,
        geom_col="geom",
        filtros_map={
            "bioma": QueimadaEvento.bioma,
            "sensor": QueimadaEvento.fonte_sensor,
            "periodo": QueimadaEvento.data_ocorrencia,
        },
        tipo_feature="queimada",
        geom_tipo="point",
    ),
    Dominio.DESMATAMENTO: DomainSpec(
        model=DesmatamentoAlerta,
        geom_col="geom",
        filtros_map={
            "tipo_alerta": DesmatamentoAlerta.tipo_alerta,
            "periodo": DesmatamentoAlerta.data_ocorrencia,
        },
        tipo_feature="desmatamento",
        geom_tipo="polygon",
    ),
    Dominio.UNIDADE_CONSERVACAO: DomainSpec(
        model=UnidadeConservacao,
        geom_col="geom",
        filtros_map={
            "categoria_uc": UnidadeConservacao.categoria,
            "esfera_uc": UnidadeConservacao.esfera,
            "grupo_snuc": UnidadeConservacao.grupo_snuc,
        },
        tipo_feature="unidade_conservacao",
        geom_tipo="polygon",
    ),
    Dominio.TERRA_INDIGENA: DomainSpec(
        model=TerraIndigena,
        geom_col="geom",
        filtros_map={
            "fase_ti": TerraIndigena.fase,
        },
        tipo_feature="terra_indigena",
        geom_tipo="polygon",
    ),
    Dominio.QUILOMBOLA: DomainSpec(
        model=TerritorioQuilombola,
        geom_col="geom",
        filtros_map={},
        tipo_feature="quilombola",
        geom_tipo="polygon",
    ),
    Dominio.ASSENTAMENTO: DomainSpec(
        model=AssentamentoRural,
        geom_col="geom",
        filtros_map={},
        tipo_feature="assentamento_rural",
        geom_tipo="polygon",
    ),
    Dominio.IMOVEL_RURAL: DomainSpec(
        model=ImovelRural,
        geom_col="geom",
        filtros_map={},
        tipo_feature="imovel_rural",
        geom_tipo="polygon",
    ),
    Dominio.CAMADA_ESTADUAL: DomainSpec(
        model=CamadaEstadualAmbiental,
        geom_col="geom",
        filtros_map={},
        tipo_feature="camada_estadual",
        geom_tipo="polygon",
    ),
}
