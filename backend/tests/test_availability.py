"""Availability status calculation regressions."""

from datetime import timedelta
from types import SimpleNamespace

from app.services.availability_service import _ports, agent_is_online
from app.utils.time import utcnow_naive


def test_agent_recent_heartbeat_is_online():
    now = utcnow_naive()
    agent = SimpleNamespace(is_active=True, last_heartbeat=now - timedelta(seconds=30))
    assert agent_is_online(agent, now) is True


def test_agent_stale_heartbeat_is_offline():
    now = utcnow_naive()
    agent = SimpleNamespace(is_active=True, last_heartbeat=now - timedelta(minutes=10))
    assert agent_is_online(agent, now) is False


def test_disabled_agent_is_not_online():
    now = utcnow_naive()
    agent = SimpleNamespace(is_active=False, last_heartbeat=now)
    assert agent_is_online(agent, now) is False


def test_ports_accepts_numbers_and_discovery_objects():
    device = SimpleNamespace(open_ports=[22, {"port": 443}, "8080", {"port": "invalid"}])
    assert _ports(device) == [22, 443, 8080]
