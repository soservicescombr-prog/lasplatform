"""Helpers de data/hora compatíveis com o schema legado do NetGuard."""

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Retorna UTC sem tzinfo para colunas PostgreSQL TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
