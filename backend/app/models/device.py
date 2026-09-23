# netguard/backend/app/models/device.py
"""
NetGuard - Modelo de Dispositivos descobertos na rede.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Enum, Text, Integer, Float,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, MACADDR
from sqlalchemy.orm import relationship
from app.database import Base


class DeviceType(str, enum.Enum):
    SWITCH = "switch"
    ROUTER = "router"
    FIREWALL = "firewall"
    SERVER = "server"
    DESKTOP = "desktop"
    PRINTER = "printer"
    ACCESS_POINT = "access_point"
    IP_PHONE = "ip_phone"
    CAMERA = "camera"
    IOT = "iot"
    UNKNOWN = "unknown"


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNREACHABLE = "unreachable"


class Device(Base):
    __tablename__ = "devices"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    ip_address = Column(INET, nullable=False, index=True)
    mac_address = Column(MACADDR, nullable=True, index=True)
    hostname = Column(String(255), nullable=True)
    fqdn = Column(String(500), nullable=True)
    device_type = Column(
        Enum(DeviceType),
        default=DeviceType.UNKNOWN,
        nullable=False,
    )
    status = Column(
        Enum(DeviceStatus),
        default=DeviceStatus.ONLINE,
        nullable=False,
    )

    # Identification
    vendor = Column(String(200), nullable=True)
    model = Column(String(200), nullable=True)
    serial_number = Column(String(200), nullable=True)
    firmware_version = Column(String(100), nullable=True)
    os_name = Column(String(200), nullable=True)
    os_version = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)

    # SNMP
    snmp_enabled = Column(Boolean, default=False, nullable=False)
    snmp_version = Column(String(10), nullable=True)
    snmp_community_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    snmp_sys_descr = Column(Text, nullable=True)
    snmp_sys_name = Column(String(255), nullable=True)
    snmp_sys_location = Column(String(255), nullable=True)
    snmp_sys_contact = Column(String(255), nullable=True)
    snmp_sys_uptime = Column(String(100), nullable=True)
    snmp_sys_object_id = Column(String(255), nullable=True)

    # Network
    network_segment = Column(String(50), nullable=True)
    open_ports = Column(JSONB, nullable=True, default=[])

    # Management
    is_visible = Column(Boolean, default=True, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    tags = Column(JSONB, nullable=True, default=[])
    notes = Column(Text, nullable=True)
    custom_fields = Column(JSONB, nullable=True, default={})

    # Performance metrics (latest)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)

    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    snmp_interfaces = relationship(
        "SNMPInterface",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    vulnerability_findings = relationship(
        "VulnerabilityFinding",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    alerts = relationship(
        "Alert",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    agent = relationship(
        "AgentRegistration",
        back_populates="device",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Device {self.ip_address} ({self.device_type.value})>"
