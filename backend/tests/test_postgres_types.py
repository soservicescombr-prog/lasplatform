"""Regressões de tipagem dos campos específicos do PostgreSQL."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import asyncpg

from app.models.device import Device
from app.utils.postgres import as_inet


def test_inet_comparison_uses_explicit_database_cast():
    statement = select(Device.id).where(
        Device.ip_address == as_inet("192.168.0.1")
    )

    compiled = str(statement.compile(dialect=asyncpg.dialect()))

    assert "devices.ip_address = CAST(" in compiled
    assert " AS INET)" in compiled
    assert "::VARCHAR" not in compiled
