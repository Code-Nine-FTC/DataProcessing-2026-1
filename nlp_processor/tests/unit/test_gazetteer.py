# -*- coding: utf-8 -*-
import pytest

from nlp_processor.infrastructure import gazetteer


@pytest.fixture(autouse=True)
def _municipios_em_memoria(monkeypatch):
    """Semeia o gazetteer sem banco e força a busca linear (sem ahocorasick)."""
    monkeypatch.setattr(gazetteer, "_municipios", {"sao paulo", "campinas", "santos"})
    monkeypatch.setattr(gazetteer, "_aut_municipios", None)


def test_sao_paulo_sozinho_e_a_capital():
    assert gazetteer.encontrar_municipio("queimadas em sao paulo") == "sao paulo"


def test_estado_de_sao_paulo_nao_resolve_municipio():
    # "estado de são paulo" => estado inteiro => sem recorte de município.
    assert gazetteer.encontrar_municipio("queimadas no estado de sao paulo") is None


def test_estado_sao_paulo_sem_de_tambem_e_estado():
    assert gazetteer.encontrar_municipio("queimadas no estado sao paulo") is None


def test_estado_de_sp_tambem_e_estado():
    assert gazetteer.encontrar_municipio("desmatamento no estado de sp") is None


def test_cidade_de_sao_paulo_e_a_capital():
    assert gazetteer.encontrar_municipio("queimadas na cidade de sao paulo") == "sao paulo"


def test_capital_do_estado_de_sao_paulo_e_a_capital():
    # marcador explícito de capital tem prioridade sobre a menção ao estado.
    assert (
        gazetteer.encontrar_municipio("queimadas na capital do estado de sao paulo")
        == "sao paulo"
    )


def test_estado_distante_de_sao_paulo_ainda_e_capital():
    # "estado" precisa vir JUNTO de "são paulo"; aqui não vem.
    assert (
        gazetteer.encontrar_municipio("estado de conservacao das ucs em sao paulo")
        == "sao paulo"
    )


def test_outro_municipio_nao_e_afetado():
    assert gazetteer.encontrar_municipio("queimadas em campinas") == "campinas"
