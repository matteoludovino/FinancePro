"""Errors the web app can show as they come: `detail` is a sentence in Portuguese, `errors` maps fields."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_ROOTS = {"body", "query", "path", "header", "cookie"}


def _message(error: dict[str, Any], field: str) -> str:
    kind = error["type"]
    ctx = error.get("ctx") or {}
    if kind == "missing":
        return "Campo obrigatório."
    if kind == "string_too_short":
        return (
            "Campo obrigatório."
            if ctx.get("min_length") == 1
            else f"Use pelo menos {ctx['min_length']} caracteres."
        )
    if kind == "string_too_long":
        return f"Use no máximo {ctx['max_length']} caracteres."
    if kind in {"greater_than_equal", "less_than_equal", "greater_than", "less_than"}:
        return "Valor fora do intervalo permitido."
    if kind in {"enum", "literal_error"}:
        return "Opção inválida."
    if kind == "value_error":
        if field.endswith("email"):
            return "E-mail inválido."
        # Our own validators raise ValueError with a message already written for the user.
        return str(ctx.get("error") or error["msg"]).removeprefix("Value error, ")
    return "Valor inválido."


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    errors: dict[str, str] = {}
    for error in exc.errors() if isinstance(exc, RequestValidationError) else []:
        field = ".".join(str(part) for part in error["loc"] if part not in _ROOTS) or "_"
        errors.setdefault(field, _message(error, field))
    detail = next(iter(errors.values()), "Dados inválidos.")
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
