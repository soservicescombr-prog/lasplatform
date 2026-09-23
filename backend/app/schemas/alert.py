# netguard/backend/app/schemas/alert.py
"""
NetGuard - Schemas de Alertas e Regras de Alerta (Pydantic).
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


# === Alert ===

class AlertResponse(BaseModel):
    id: UUID
    device_id: Optional[UUID] = None
    title: str
    message: Optional[str] = None
    severity: str
    category: str
    status: str
    is_muted: bool
    muted_until: Optional[datetime] = None
    muted_reason: Optional[str] = None
    occurrence_count: int
    triggered_at: datetime
    last_occurrence: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    details: Optional[dict] = None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int


class AlertMuteRequest(BaseModel):
    duration_minutes: Optional[int] = None  # None = indefinido
    reason: Optional[str] = None


class AlertAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class AlertSummary(BaseModel):
    total_active: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    muted: int = 0
    acknowledged: int = 0
    device_offline: int = 0
    agent_offline: int = 0


# === Alert Rule ===

class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    category: str
    severity: str = "medium"
    condition_type: str
    condition_params: dict[str, Any] = {}
    threshold_value: Optional[float] = None
    threshold_operator: Optional[str] = None
    notify_email: bool = False
    notify_webhook: bool = False
    webhook_url: Optional[str] = None
    cooldown_minutes: int = 15


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None
    condition_params: Optional[dict] = None
    threshold_value: Optional[float] = None
    notify_email: Optional[bool] = None
    notify_webhook: Optional[bool] = None
    webhook_url: Optional[str] = None
    cooldown_minutes: Optional[int] = None


class AlertRuleResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    category: str
    severity: str
    is_active: bool
    condition_type: str
    condition_params: dict
    threshold_value: Optional[float] = None
    threshold_operator: Optional[str] = None
    notify_email: bool
    notify_webhook: bool
    cooldown_minutes: int
    created_at: datetime

    model_config = {"from_attributes": True}
