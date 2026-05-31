import json

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from api.utils.error_handlers import (
    AppException,
    app_exception_handler,
    database_exception_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def _body(response) -> dict:
    return json.loads(response.body)


@pytest.mark.asyncio
async def test_http_exception_uses_standard_error_payload():
    response = await http_exception_handler(
        _request("/http-error"),
        HTTPException(status_code=404, detail="Recurso não encontrado."),
    )

    assert response.status_code == 404
    assert _body(response) == {
        "error": {
            "code": "not_found",
            "message": "Recurso não encontrado.",
            "path": "/http-error",
        }
    }


@pytest.mark.asyncio
async def test_app_exception_uses_standard_error_payload_with_details():
    response = await app_exception_handler(
        _request("/app-error"),
        AppException(
            "Não foi possível concluir a operação.",
            status_code=400,
            code="operation_error",
            details={"campo": "valor inválido"},
        ),
    )

    assert response.status_code == 400
    assert _body(response) == {
        "error": {
            "code": "operation_error",
            "message": "Não foi possível concluir a operação.",
            "path": "/app-error",
            "details": {"campo": "valor inválido"},
        }
    }


@pytest.mark.asyncio
async def test_validation_error_uses_standard_error_payload():
    response = await validation_exception_handler(
        _request("/items/abc"),
        RequestValidationError(
            [
                {
                    "type": "int_parsing",
                    "loc": ("path", "item_id"),
                    "msg": "Input should be a valid integer",
                    "input": "abc",
                }
            ]
        ),
    )

    assert response.status_code == 422
    body = _body(response)
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Erro de validação nos dados da requisição."
    assert body["error"]["path"] == "/items/abc"
    assert body["error"]["details"][0]["loc"] == ["path", "item_id"]


@pytest.mark.asyncio
async def test_database_error_does_not_expose_internal_details():
    response = await database_exception_handler(
        _request("/db-error"),
        SQLAlchemyError("detalhe interno do banco"),
    )

    assert response.status_code == 500
    assert _body(response) == {
        "error": {
            "code": "database_error",
            "message": "Erro ao acessar o banco de dados.",
            "path": "/db-error",
        }
    }
    assert "detalhe interno" not in response.body.decode()


@pytest.mark.asyncio
async def test_unexpected_error_does_not_expose_internal_details():
    response = await unexpected_exception_handler(
        _request("/unexpected-error"),
        RuntimeError("detalhe interno inesperado"),
    )

    assert response.status_code == 500
    assert _body(response) == {
        "error": {
            "code": "internal_server_error",
            "message": "Erro interno do servidor.",
            "path": "/unexpected-error",
        }
    }
    assert "detalhe interno" not in response.body.decode()
