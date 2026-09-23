# netguard/backend/app/models/snmp.py
"""
NetGuard - Modelos SNMP: Communities, Coletas e Interfaces.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    Float, ForeignKey, BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class SNMPCommunity(Base):
    """Communities SNMP cadastradas para coleta."""
    __tablename__ = "snmp_communities"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = Column(String(100), nullable=False)
    community_string = Column(String(255), nullable=False)
    snmp_version = Column(String(10), default="v2c", nullable=False)

    # SNMPv3 fields
    security_name = Column(String(100), nullable=True)
    auth_protocol = Column(String(10), nullable=True)  # MD5, SHA
    auth_password = Column(String(255), nullable=True)
    priv_protocol = Column(String(10), nullable=True)  # DES, AES
    priv_password = Column(String(255), nullable=True)
    security_level = Column(String(30), nullable=True)

    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SNMPCommunity {self.name} ({self.snmp_version})>"


class SNMPCollection(Base):
    """Registro de cada coleta SNMP realizada."""
    __tablename__ = "snmp_collections"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("snmp_communities.id", ondelete="SET NULL"),
        nullable=True,
    )
    collection_data = Column(JSONB, nullable=True)
    status = Column(String(20), default="completed", nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<SNMPCollection {self.device_id} at {self.collected_at}>"


class SNMPInterface(Base):
    """Dados de interfaces coletados via SNMP (ifTable/ifXTable)."""
    __tablename__ = "snmp_interfaces"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    if_index = Column(Integer, nullable=False)
    if_name = Column(String(255), nullable=True)
    if_descr = Column(String(500), nullable=True)
    if_alias = Column(String(255), nullable=True)
    if_type = Column(Integer, nullable=True)
    if_type_name = Column(String(100), nullable=True)
    if_mtu = Column(Integer, nullable=True)
    if_speed = Column(BigInteger, nullable=True)
    if_high_speed = Column(BigInteger, nullable=True)
    if_phys_address = Column(String(50), nullable=True)
    if_admin_status = Column(Integer, nullable=True)  # 1=up, 2=down, 3=testing
    if_oper_status = Column(Integer, nullable=True)   # 1=up, 2=down, etc.

    # Counters (latest snapshot)
    if_in_octets = Column(BigInteger, default=0)
    if_out_octets = Column(BigInteger, default=0)
    if_in_errors = Column(BigInteger, default=0)
    if_out_errors = Column(BigInteger, default=0)
    if_in_discards = Column(BigInteger, default=0)
    if_out_discards = Column(BigInteger, default=0)
    if_in_ucast_pkts = Column(BigInteger, default=0)
    if_out_ucast_pkts = Column(BigInteger, default=0)
    if_in_broadcast_pkts = Column(BigInteger, default=0)
    if_out_broadcast_pkts = Column(BigInteger, default=0)

    # Calculated rates (per second, from delta)
    in_bps = Column(Float, nullable=True)
    out_bps = Column(Float, nullable=True)
    in_error_rate = Column(Float, nullable=True)
    out_error_rate = Column(Float, nullable=True)
    utilization_in = Column(Float, nullable=True)   # percentage
    utilization_out = Column(Float, nullable=True)   # percentage

    # History
    metrics_history = Column(JSONB, nullable=True, default=[])

    last_collected = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    device = relationship("Device", back_populates="snmp_interfaces")

    def __repr__(self) -> str:
        return f"<SNMPInterface {self.if_name} on {self.device_id}>"
