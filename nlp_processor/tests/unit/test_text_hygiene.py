# -*- coding: utf-8 -*-
import pytest

from nlp_processor.pipeline.text_hygiene import processar


def test_higieniza_espacos_multiplos():
    resultado = processar("queimadas   em   campinas")
    assert "  " not in resultado.corrigido


def test_normaliza_para_minusculo():
    resultado = processar("QUEIMADAS EM CAMPINAS")
    assert resultado.normalizado == resultado.normalizado.lower()


def test_remove_acentos_no_normalizado():
    resultado = processar("queimadas em São Paulo")
    assert "ã" not in resultado.normalizado


def test_preserva_acentos_no_corrigido():
    resultado = processar("queimadas em São Paulo")
    assert resultado.corrigido != resultado.normalizado or "ã" not in resultado.normalizado


def test_tokens_removem_stopwords():
    resultado = processar("focos de queimada em campinas")
    assert "de" not in resultado.tokens
    assert "em" not in resultado.tokens


def test_original_preservado():
    texto = "Queimadas em Campinas?"
    resultado = processar(texto)
    assert resultado.original == texto
