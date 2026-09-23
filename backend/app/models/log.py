"""Persistent Syslog events and derived log metrics."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class SyslogEvent(Base):
    """A normalized RFC 3164/5424 event received over UDP or TCP."""

    __tablename__ = "syslog_events"
    __table_args__ = (
        Index("ix_syslog_events_received_severity", "received_at", "severity"),
        Index("ix_syslog_events_source_received", "source_ip", "received_at"),
        Index("ix_syslog_events_host_received", "hostname", "received_at"),
        Index("ix_syslog_events_properties_gin", "properties", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_at = Column(DateTime, nullable=True)
    source_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=True)
    protocol = Column(String(8), nullable=False, default="udp")
    facility = Column(String(32), nullable=False, default="user", index=True)
    severity = Column(String(20), nullable=False, default="informational", index=True)
    severity_num = Column(Integer, nullable=True)
    hostname = Column(String(255), nullable=True, index=True)
    app_name = Column(String(255), nullable=True, index=True)
    proc_id = Column(String(128), nullable=True)
    msg_id = Column(String(128), nullable=True)
    message = Column(Text, nullable=False)
    raw = Column(Text, nullable=False)
    properties = Column(JSONB, nullable=False, default=dict)
    security_category = Column(String(100), nullable=True, index=True)
    security_severity = Column(String(20), nullable=True)


class LogMetric(Base):
    """Saved log query evaluated as a count metric over a sliding window."""

    __tablename__ = "log_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    filters = Column(JSONB, nullable=False, default=dict)
    window_minutes = Column(Integer, nullable=False, default=5)
    threshold = Column(Integer, nullable=False, default=1)
    minimum_span_seconds = Column(Integer, nullable=False, default=180)
    threshold_operator = Column(String(8), nullable=False, default=">=")
    severity = Column(String(20), nullable=False, default="medium")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    current_value = Column(Integer, nullable=False, default=0)
    last_evaluated_at = Column(DateTime, nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    alert_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
