# netguard/backend/app/models/scan.py
"""
NetGuard - Modelos de Scan Jobs, Vulnerabilidades e Pentest.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    Float, ForeignKey, Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.database import Base


class ScanType(str, enum.Enum):
    DISCOVERY = "discovery"
    PORT_SCAN = "port_scan"
    VULNERABILITY = "vulnerability"
    PENTEST = "pentest"
    SNMP_COLLECTION = "snmp_collection"
    FULL = "full"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SeverityLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanJob(Base):
    """Job de scan (discovery, vulnerability, pentest, etc.)."""
    __tablename__ = "scan_jobs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name = Column(String(200), nullable=False)
    scan_type = Column(Enum(ScanType), nullable=False, index=True)
    status = Column(
        Enum(ScanStatus),
        default=ScanStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Scope
    target = Column(String(500), nullable=False)  # CIDR, IP range, single IP
    target_ports = Column(String(500), nullable=True)  # e.g., "22,80,443,1-1024"
    options = Column(JSONB, nullable=True, default={})

    # Execution
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    celery_task_id = Column(String(255), nullable=True)
    progress = Column(Integer, default=0)  # 0-100
    devices_found = Column(Integer, default=0)
    vulnerabilities_found = Column(Integer, default=0)

    # Results
    results_summary = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Scheduling
    is_scheduled = Column(Boolean, default=False)
    schedule_cron = Column(String(100), nullable=True)
    next_run = Column(DateTime, nullable=True)

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    findings = relationship(
        "VulnerabilityFinding",
        back_populates="scan_job",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<ScanJob {self.name} ({self.scan_type.value}: {self.status.value})>"


class VulnerabilityFinding(Base):
    """Vulnerabilidade encontrada em um dispositivo."""
    __tablename__ = "vulnerability_findings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Vulnerability Details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(
        Enum(SeverityLevel),
        nullable=False,
        index=True,
    )
    cvss_score = Column(Float, nullable=True)

    # CVE Correlation
    cve_id = Column(String(20), nullable=True, index=True)
    cve_description = Column(Text, nullable=True)
    cve_references = Column(JSONB, nullable=True, default=[])

    # Affected Service
    port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=True)
    service_name = Column(String(100), nullable=True)
    service_version = Column(String(100), nullable=True)

    # Remediation
    remediation = Column(Text, nullable=True)
    remediation_effort = Column(String(20), nullable=True)  # low, medium, high
    fix_available = Column(Boolean, default=False)

    # State
    is_false_positive = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Evidence
    evidence = Column(JSONB, nullable=True)
    raw_output = Column(Text, nullable=True)

    # Timestamps
    first_detected = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_detected = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    device = relationship("Device", back_populates="vulnerability_findings")
    scan_job = relationship("ScanJob", back_populates="findings")

    def __repr__(self) -> str:
        return f"<VulnerabilityFinding {self.title} ({self.severity.value})>"
