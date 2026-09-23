"""Helpers para tipos específicos do PostgreSQL."""

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql.elements import Cast


def as_inet(value: str) -> Cast:
    """Converte texto em uma expressão SQL INET explicitamente tipada."""
    return cast(value, INET)
