# netguard/backend/app/models/agent.py
"""
NetGuard - Modelos de Agente (instalado em hosts para scan local).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class AgentRegistration(Base):
    """Registro de um agente instalado em um host."""
    __tablename__ = "agent_registrations"

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
        unique=True,
    )
    agent_token = Column(String(255), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)  # linux, windows
    platform_version = Column(String(100), nullable=True)
    architecture = Column(String(20), nullable=True)
    agent_version = Column(String(20), nullable=True)
    python_version = Column(String(20), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    last_heartbeat = Column(DateTime, nullable=True)
    last_report = Column(DateTime, nullable=True)

    # Config
    scan_interval_minutes = Column(Integer, default=60)
    auto_update = Column(Boolean, default=True)
    config = Column(JSONB, nullable=True, default={})

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    device = relationship("Device", back_populates="agent")
    reports = relationship(
        "AgentReport",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<AgentRegistration {self.hostname} ({self.platform})>"


class AgentReport(Base):
    """Relatório enviado pelo agente com resultados do scan local."""
    __tablename__ = "agent_reports"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    report_type = Column(String(50), nullable=False)
    os_info = Column(JSONB, nullable=True)
    installed_software = Column(JSONB, nullable=True)
    running_services = Column(JSONB, nullable=True)
    open_ports = Column(JSONB, nullable=True)
    pending_updates = Column(JSONB, nullable=True)
    vulnerabilities = Column(JSONB, nullable=True)
    security_config = Column(JSONB, nullable=True)
    runtime_versions = Column(JSONB, nullable=True)

    total_vulnerabilities = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)

    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    agent = relationship("AgentRegistration", back_populates="reports")

    def __repr__(self) -> str:
        return f"<AgentReport {self.report_type} at {self.created_at}>"
