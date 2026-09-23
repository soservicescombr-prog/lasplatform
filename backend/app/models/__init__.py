# netguard/backend/app/models/__init__.py
"""
NetGuard - Models Registry.
Importa todos os modelos para garantir que o Alembic os detecte.
"""

from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.models.device import Device, DeviceType, DeviceStatus
from app.models.snmp import SNMPCommunity, SNMPCollection, SNMPInterface
from app.models.scan import (
    ScanJob, ScanType, ScanStatus,
    VulnerabilityFinding, SeverityLevel,
)
from app.models.alert import Alert, AlertStatus, AlertRule
from app.models.agent import AgentRegistration, AgentReport
from app.models.inventory import InventoryItem, NetworkConnection
from app.models.log import SyslogEvent, LogMetric
from app.models.metric import DeviceMetric, AgentMetric, AgentBaseline, AgentAnomalyEvent

__all__ = [
    "User", "UserRole",
    "AuditLog",
    "Device", "DeviceType", "DeviceStatus",
    "SNMPCommunity", "SNMPCollection", "SNMPInterface",
    "ScanJob", "ScanType", "ScanStatus",
    "VulnerabilityFinding", "SeverityLevel",
    "Alert", "AlertStatus", "AlertRule",
    "AgentRegistration", "AgentReport",
    "InventoryItem", "NetworkConnection",
    "SyslogEvent", "LogMetric",
    "DeviceMetric", "AgentMetric", "AgentBaseline", "AgentAnomalyEvent",
]
