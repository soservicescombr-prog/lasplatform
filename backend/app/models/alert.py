# netguard/backend/app/models/alert.py
"""
NetGuard - Modelos de Alertas e Regras de Alerta.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    Float, ForeignKey, Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    MUTED = "muted"
    RESOLVED = "resolved"


class Alert(Base):
    """Alerta gerado pelo sistema."""
    __tablename__ = "alerts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="medium", index=True)
    category = Column(String(50), nullable=False, index=True)
    status = Column(
        Enum(AlertStatus),
        default=AlertStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Mute control
    is_muted = Column(Boolean, default=False, nullable=False)
    muted_until = Column(DateTime, nullable=True)
    muted_by = Column(UUID(as_uuid=True), nullable=True)
    muted_reason = Column(String(500), nullable=True)

    # Resolution
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Details
    details = Column(JSONB, nullable=True)
    notification_sent = Column(Boolean, default=False)
    occurrence_count = Column(Integer, default=1)

    # Timestamps
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_occurrence = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    device = relationship("Device", back_populates="alerts")
    rule = relationship("AlertRule", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert {self.title} ({self.status.value})>"


class AlertRule(Base):
    """Regra de alerta configurável."""
    __tablename__ = "alert_rules"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default="medium")
    is_active = Column(Boolean, default=True, nullable=False)

    # Condition
    condition_type = Column(String(50), nullable=False)
    condition_params = Column(JSONB, nullable=False, default={})
    threshold_value = Column(Float, nullable=True)
    threshold_operator = Column(String(10), nullable=True)

    # Notification
    notify_email = Column(Boolean, default=False)
    notify_webhook = Column(Boolean, default=False)
    webhook_url = Column(String(500), nullable=True)
    cooldown_minutes = Column(Integer, default=15)

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    alerts = relationship("Alert", back_populates="rule", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<AlertRule {self.name}>"
