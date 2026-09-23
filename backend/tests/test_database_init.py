import pytest

import app.database as database


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.run_sync_called = False

    async def execute(self, statement):
        self.statements.append(str(statement))

    async def run_sync(self, callback):
        self.run_sync_called = True


class FakeBegin:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return FakeBegin(self.connection)


@pytest.mark.asyncio
async def test_init_db_acquires_postgres_advisory_lock(monkeypatch):
    fake_engine = FakeEngine()
    monkeypatch.setattr(database, 'engine', fake_engine)

    await database.init_db()

    assert fake_engine.connection.run_sync_called
    assert fake_engine.connection.statements[0] == 'SELECT pg_advisory_xact_lock(2026092301)'
    assert fake_engine.connection.statements[1:] == list(database.COMPATIBILITY_MIGRATIONS)
    assert any('device_metrics ADD COLUMN IF NOT EXISTS details' in item for item in fake_engine.connection.statements)
    assert any('agent_metrics ADD COLUMN IF NOT EXISTS load_15m' in item for item in fake_engine.connection.statements)
    assert any('agent_metrics ADD COLUMN IF NOT EXISTS details' in item for item in fake_engine.connection.statements)
