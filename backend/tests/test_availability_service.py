from datetime import timedelta
from types import SimpleNamespace

from app.services.availability_service import agent_is_online
from app.utils.time import utcnow_naive


def test_agent_is_online_respects_heartbeat_window():
    now = utcnow_naive()
    assert agent_is_online(SimpleNamespace(is_active=True, last_heartbeat=now), now)
    assert not agent_is_online(SimpleNamespace(is_active=True, last_heartbeat=now - timedelta(hours=1)), now)
    assert not agent_is_online(SimpleNamespace(is_active=False, last_heartbeat=now), now)
    assert not agent_is_online(SimpleNamespace(is_active=True, last_heartbeat=None), now)

