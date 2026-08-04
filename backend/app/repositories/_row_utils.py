"""Wspólne mapowanie typów asyncpg → DTO (str/float).

asyncpg zwraca `uuid.UUID` i `Decimal` — Pydantic `response_model` z polami `str`/`float`
rzuca ResponseValidationError (500). Przeglądarka często pokazuje to jako „CORS Missing
Allow Origin”, bo odpowiedź błędu bywa bez ACAO. Ten sam wzorzec co w `templates_repo`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID


def stringify_uuid(value: Any) -> Any:
    return str(value) if isinstance(value, UUID) else value


def as_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_row_mapping(
    mapping: dict[str, Any],
    *,
    uuid_keys: tuple[str, ...] = (),
    float_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    out = dict(mapping)
    for key in uuid_keys:
        if key in out:
            out[key] = stringify_uuid(out[key])
    for key in float_keys:
        if key in out:
            out[key] = as_float(out[key])
    return out
