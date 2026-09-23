"""Validação da normalização defensiva usada pelos endpoints de dispositivos."""

from datetime import datetime, timezone
from ipaddress import ip_address
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.endpoints.devices import _device_payload
from app.models.device import DeviceStatus, DeviceType
from app.schemas.device import DeviceResponse


def test_endpoint_payload_converts_database_network_types():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    device = SimpleNamespace(
        id=uuid4(), ip_address=ip_address("192.168.0.51"), mac_address=None,
        hostname=None, fqdn=None, device_type=DeviceType.UNKNOWN,
        status=DeviceStatus.ONLINE, vendor=None, model=None, os_name=None,
        os_version=None, image_url=None, snmp_enabled=False,
        snmp_sys_name=None, snmp_sys_location=None, snmp_sys_uptime=None,
        network_segment=None, open_ports=[], is_visible=True, is_pinned=False,
        tags=[], cpu_usage=None, memory_usage=None, disk_usage=None,
        first_seen=now, last_seen=now, created_at=now,
    )

    payload = _device_payload(device)
    response = DeviceResponse.model_validate(payload)

    assert payload["ip_address"] == "192.168.0.51"
    assert response.model_dump(mode="json")["ip_address"] == "192.168.0.51"
