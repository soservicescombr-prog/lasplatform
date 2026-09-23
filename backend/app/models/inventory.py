# netguard/backend/app/models/inventory.py
"""
NetGuard - Modelo de Inventário/CMDB com campos customizáveis.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class InventoryItem(Base):
    """Item de inventário/CMDB vinculado a um dispositivo."""
    __tablename__ = "inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)

    # Asset management
    asset_tag = Column(String(100), nullable=True, unique=True)
    serial_number = Column(String(200), nullable=True)
    purchase_date = Column(DateTime, nullable=True)
    warranty_expiry = Column(DateTime, nullable=True)
    purchase_cost = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    responsible = Column(String(200), nullable=True)
    location_building = Column(String(200), nullable=True)
    location_floor = Column(String(50), nullable=True)
    location_room = Column(String(100), nullable=True)
    location_rack = Column(String(50), nullable=True)
    location_rack_unit = Column(String(20), nullable=True)

    # Classification
    criticality = Column(String(20), default="medium")  # critical, high, medium, low
    environment = Column(String(50), nullable=True)  # production, staging, dev, test
    business_service = Column(String(200), nullable=True)
    application = Column(String(200), nullable=True)

    # Contracts & support
    support_contract = Column(String(200), nullable=True)
    support_expiry = Column(DateTime, nullable=True)
    support_vendor = Column(String(200), nullable=True)
    support_phone = Column(String(50), nullable=True)

    # Custom fields (JSON)
    custom_fields = Column(JSONB, nullable=True, default={})
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<InventoryItem {self.asset_tag}>"


class NetworkConnection(Base):
    """Conexão entre dispositivos (para topologia)."""
    __tablename__ = "network_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    target_device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    source_interface = Column(String(100), nullable=True)
    target_interface = Column(String(100), nullable=True)
    connection_type = Column(String(50), default="ethernet")  # ethernet, wifi, vpn, trunk
    bandwidth = Column(String(50), nullable=True)
    status = Column(String(20), default="active")
    discovered_via = Column(String(50), nullable=True)  # cdp, lldp, arp, manual
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<NetworkConnection {self.source_device_id} → {self.target_device_id}>"
