# -*- coding: utf-8 -*-
import asyncio

import pytest

from nlp_processor.domain.enums import Dominio, Operacao
from nlp_processor.pipeline import semantic_router, text_hygiene


@pytest.fixture(scope="module", autouse=True)
def aquece_router():
    asyncio.get_event_loop().run_until_complete(semantic_router.warm_up())


def _rotear(pergunta: str):
    texto = text_hygiene.processar(pergunta)
    return asyncio.get_event_loop().run_until_complete(
        semantic_router.entender(texto)
    )


def test_queimada_listar():
    plano = _rotear("focos de queimada em Campinas")
    assert any(s.dominio == Dominio.QUEIMADA for s in plano.specs)


def test_queimada_rankear():
    plano = _rotear("qual município tem mais queimadas em SP")
    assert any(
        s.dominio == Dominio.QUEIMADA and s.operacao == Operacao.RANKEAR
        for s in plano.specs
    )


def test_desmatamento_listar():
    plano = _rotear("alertas de desmatamento detectados")
    assert any(s.dominio == Dominio.DESMATAMENTO for s in plano.specs)


def test_terra_indigena():
    plano = _rotear("terras indígenas em Bauru")
    assert any(s.dominio == Dominio.TERRA_INDIGENA for s in plano.specs)


def test_quilombola():
    plano = _rotear("territórios quilombolas no Vale do Ribeira")
    assert any(s.dominio == Dominio.QUILOMBOLA for s in plano.specs)


def test_imovel_rural():
    plano = _rotear("imóveis rurais em Ribeirão Preto")
    assert any(s.dominio == Dominio.IMOVEL_RURAL for s in plano.specs)


def test_fora_escopo_outro_estado():
    plano = _rotear("queimadas no Pará")
    assert plano.fora_escopo


def test_contexto_espacial_ti():
    plano = _rotear("queimadas dentro de terras indígenas")
    spec_q = next((s for s in plano.specs if s.dominio == Dominio.QUEIMADA), None)
    assert spec_q is not None
    assert spec_q.contexto_espacial is not None
    assert spec_q.contexto_espacial.dentro_de == Dominio.TERRA_INDIGENA
