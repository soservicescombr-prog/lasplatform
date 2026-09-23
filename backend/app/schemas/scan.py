# netguard/backend/app/schemas/scan.py
"""
NetGuard - Schemas de Scan e Vulnerabilidades (Pydantic).
"""

from datetime import datetime
from typing import Optional, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# === Scan Job ===

class ScanJobCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    scan_type: str  # discovery, port_scan, vulnerability, pentest, full
    target: str = Field(..., min_length=1)
    target_ports: Optional[str] = None
    options: dict[str, Any] = Field(default_factory=dict)
    is_scheduled: bool = False
    schedule_cron: Optional[str] = None
    schedule_frequency: Optional[Literal["daily", "weekly", "biweekly", "monthly", "custom"]] = None
    schedule_time: str = Field(default="02:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    schedule_days: list[int] = Field(default_factory=list)
    schedule_day_of_month: int = Field(default=1, ge=1, le=28)

    @model_validator(mode="after")
    def validate_schedule(self):
        if not self.is_scheduled:
            return self
        if not self.schedule_frequency:
            raise ValueError("Selecione a frequência do agendamento")
        if self.schedule_frequency in {"weekly", "custom"}:
            if not self.schedule_days or any(day < 0 or day > 6 for day in self.schedule_days):
                raise ValueError("Selecione ao menos um dia da semana válido")
        return self


class ScanJobResponse(BaseModel):
    id: UUID
    name: str
    scan_type: str
    status: str
    target: str
    target_ports: Optional[str] = None
    celery_task_id: Optional[str] = None
    progress: int
    devices_found: int
    vulnerabilities_found: int
    results_summary: Optional[dict] = None
    error_message: Optional[str] = None
    is_scheduled: bool
    schedule_cron: Optional[str] = None
    options: Optional[dict[str, Any]] = None
    next_run: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanJobListResponse(BaseModel):
    items: list[ScanJobResponse]
    total: int
    page: int
    page_size: int


# === Vulnerability Finding ===

class VulnerabilityResponse(BaseModel):
    id: UUID
    device_id: UUID
    title: str
    description: Optional[str] = None
    severity: str
    cvss_score: Optional[float] = None
    cve_id: Optional[str] = None
    cve_description: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    service_name: Optional[str] = None
    service_version: Optional[str] = None
    remediation: Optional[str] = None
    remediation_effort: Optional[str] = None
    fix_available: bool
    is_false_positive: bool
    is_resolved: bool
    evidence: Optional[dict] = None
    first_detected: datetime
    last_detected: datetime

    model_config = {"from_attributes": True}


class VulnerabilityListResponse(BaseModel):
    items: list[VulnerabilityResponse]
    total: int
    page: int
    page_size: int
    by_severity: dict[str, int] = {}


class VulnerabilitySummary(BaseModel):
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    resolved: int = 0
    false_positives: int = 0
