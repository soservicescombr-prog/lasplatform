"""Regressões da confirmação do job antes da publicação no Celery."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints.scans import create_scan
from app.models.scan import ScanStatus
from app.schemas.scan import ScanJobCreate
from app.tasks import celery_app


class FakeSession:
    def __init__(self):
        self.events: list[str] = []
        self.scan = None

    def add(self, scan):
        self.scan = scan
        self.events.append("add")

    async def commit(self):
        self.events.append("commit")
        if self.scan.id is None:
            self.scan.id = uuid4()
        if self.scan.status is None:
            self.scan.status = ScanStatus.PENDING
        if self.scan.progress is None:
            self.scan.progress = 0
        if self.scan.devices_found is None:
            self.scan.devices_found = 0
        if self.scan.vulnerabilities_found is None:
            self.scan.vulnerabilities_found = 0
        if self.scan.is_scheduled is None:
            self.scan.is_scheduled = False

    async def refresh(self, _scan):
        self.events.append("refresh")


@pytest.mark.asyncio
async def test_scan_is_committed_before_celery_publish(monkeypatch):
    db = FakeSession()

    def send_task(*_args, **kwargs):
        db.events.append("send_task")
        assert "commit" in db.events
        assert kwargs["queue"] == "scans"
        return SimpleNamespace(id="celery-task-id")

    monkeypatch.setattr(celery_app, "send_task", send_task)

    scan = await create_scan(
        ScanJobCreate(
            name="Teste de corrida",
            scan_type="discovery",
            target="192.168.0.0/29",
            options={"profile": "quick"},
        ),
        db=db,
        operator=SimpleNamespace(id=uuid4()),
    )

    assert db.events.index("commit") < db.events.index("send_task")
    assert scan.celery_task_id == "celery-task-id"
    assert scan.status == ScanStatus.PENDING
