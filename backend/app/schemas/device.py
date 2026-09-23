# netguard/backend/app/schemas/device.py
"""
NetGuard - Schemas de Dispositivos (Pydantic).
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator


class DeviceBase(BaseModel):
    ip_address: str
    hostname: Optional[str] = None
    device_type: str = "unknown"
    notes: Optional[str] = None
    tags: list[str] = []


class DeviceCreate(DeviceBase):
    mac_address: Optional[str] = None
    network_segment: Optional[str] = None


class DeviceUpdate(BaseModel):
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    is_visible: Optional[bool] = None
    is_pinned: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None


class DeviceResponse(BaseModel):
    id: UUID
    ip_address: IPvAnyAddress
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    fqdn: Optional[str] = None
    device_type: str
    status: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    image_url: Optional[str] = None
    snmp_enabled: bool
    snmp_sys_name: Optional[str] = None
    snmp_sys_location: Optional[str] = None
    snmp_sys_uptime: Optional[str] = None
    network_segment: Optional[str] = None
    open_ports: Optional[list] = None
    is_visible: bool
    is_pinned: bool
    tags: list[str] = []
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    first_seen: datetime
    last_seen: datetime
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def serialize_ip_address(cls, value):
        """asyncpg retorna INET como IPv4Address/IPv6Address."""
        return str(value)

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int
    snmp_active_count: int = 0
    snmp_inactive_count: int = 0


class DeviceSummary(BaseModel):
    total_devices: int = 0
    online: int = 0
    offline: int = 0
    snmp_active: int = 0
    snmp_inactive: int = 0
    by_type: dict[str, int] = {}
    new_last_24h: int = 0
