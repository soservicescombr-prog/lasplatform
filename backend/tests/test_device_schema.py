"""Regressões da serialização de tipos PostgreSQL dos dispositivos."""

from datetime import datetime
from ipaddress import ip_address
from uuid import uuid4

from app.schemas.device import DeviceResponse


def test_device_response_serializes_inet_objects_as_strings():
    now = datetime.utcnow()
    response = DeviceResponse.model_validate({
        "id": uuid4(),
        "ip_address": ip_address("192.168.0.1"),
        "device_type": "router",
        "status": "online",
        "snmp_enabled": False,
        "is_visible": True,
        "is_pinned": False,
        "tags": [],
        "first_seen": now,
        "last_seen": now,
        "created_at": now,
    })

    assert str(response.ip_address) == "192.168.0.1"
    assert response.model_dump(mode="json")["ip_address"] == "192.168.0.1"
