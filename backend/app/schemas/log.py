"""API contracts for persistent logs and log-derived metrics."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LogEventResponse(BaseModel):
    id: UUID
    received_at: datetime
    event_at: Optional[datetime] = None
    source_ip: str
    source_port: Optional[int] = None
    protocol: str
    facility: str
    severity: str
    severity_num: Optional[int] = None
    hostname: Optional[str] = None
    app_name: Optional[str] = None
    proc_id: Optional[str] = None
    msg_id: Optional[str] = None
    message: str
    raw: str
    properties: dict[str, Any] = {}
    security_category: Optional[str] = None
    security_severity: Optional[str] = None

    model_config = {"from_attributes": True}


class LogEventListResponse(BaseModel):
    items: list[LogEventResponse]
    total: int
    page: int
    page_size: int


class LogMetricCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    filters: dict[str, Any] = {}
    window_minutes: int = Field(5, ge=1, le=10080)
    threshold: int = Field(10, ge=1)
    minimum_span_seconds: int = Field(180, ge=0, le=604800)
    threshold_operator: str = ">="
    severity: str = "medium"
    is_active: bool = True
    cooldown_minutes: int = Field(15, ge=1, le=10080)
    notify_email: bool = False
    notify_webhook: bool = False
    webhook_url: Optional[str] = None

    @field_validator("threshold_operator")
    @classmethod
    def valid_operator(cls, value: str) -> str:
        if value not in {">=", ">", "==", "<=", "<"}:
            raise ValueError("Operador inválido")
        return value


class LogMetricUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    window_minutes: Optional[int] = Field(None, ge=1, le=10080)
    threshold: Optional[int] = Field(None, ge=1)
    minimum_span_seconds: Optional[int] = Field(None, ge=0, le=604800)
    threshold_operator: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=10080)
    notify_email: Optional[bool] = None
    notify_webhook: Optional[bool] = None
    webhook_url: Optional[str] = None


class LogMetricResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    filters: dict[str, Any]
    window_minutes: int
    threshold: int
    minimum_span_seconds: int
    threshold_operator: str
    severity: str
    is_active: bool
    current_value: int
    last_evaluated_at: Optional[datetime] = None
    last_triggered_at: Optional[datetime] = None
    alert_rule_id: Optional[UUID] = None
    cooldown_minutes: int = 15
    notify_email: bool = False
    notify_webhook: bool = False
    webhook_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
