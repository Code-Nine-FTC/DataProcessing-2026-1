# -*- coding: utf-8 -*-
import pytest

from nlp_processor.domain.contracts import FiltrosConsulta, LocalConsulta, QuerySpec, ToolResult
from nlp_processor.domain.enums import Dominio, Operacao
from nlp_processor.pipeline.responder import compor


def _spec(dominio: Dominio, operacao: Operacao = Operacao.LISTAR) -> QuerySpec:
    return QuerySpec(
        dominio=dominio,
        operacao=operacao,
        onde=LocalConsulta(municipio_nome="Campinas"),
    )


def _resultado(dominio: Dominio, total: int, operacao: Operacao = Operacao.LISTAR) -> ToolResult:
    return ToolResult(
        dominio=dominio,
        operacao=operacao,
        total=total,
        spec=_spec(dominio, operacao),
    )


def test_resposta_com_resultado():
    resultado = _resultado(Dominio.QUEIMADA, 42)
    resposta = compor([resultado])
    assert "42" in resposta.texto
    assert resposta.status == "sucesso"


def test_resposta_sem_resultado():
    resultado = _resultado(Dominio.DESMATAMENTO, 0)
    resposta = compor([resultado])
    assert resposta.status == "sem_resultado"


def test_resposta_multiplos_dominios():
    resultados = [
        _resultado(Dominio.QUEIMADA, 10),
        _resultado(Dominio.DESMATAMENTO, 5),
    ]
    resposta = compor(resultados)
    assert "queimada" in resposta.texto.lower() or "10" in resposta.texto
    assert resposta.status == "sucesso"


def test_resposta_vazia():
    resposta = compor([])
    assert resposta.status == "sem_resultado"


def test_resposta_rankear():
    resultado = _resultado(Dominio.QUEIMADA, 3, Operacao.RANKEAR)
    resposta = compor([resultado])
    assert "ranking" in resposta.texto.lower() or "3" in resposta.texto
