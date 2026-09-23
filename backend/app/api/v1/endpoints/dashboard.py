# netguard/backend/app/api/v1/endpoints/dashboard.py
"""
NetGuard - Endpoint do Dashboard principal.
Agrega dados de todos os módulos para a visão geral.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.device import Device, DeviceStatus
from app.models.scan import ScanJob, ScanStatus, VulnerabilityFinding, SeverityLevel
from app.models.alert import Alert, AlertStatus
from app.models.agent import AgentRegistration
from app.utils.time import utcnow_naive
from app.services.availability_service import agent_is_online

router = APIRouter()


@router.get("/overview")
async def dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna visão geral do dashboard com métricas de todos os módulos."""

    now = utcnow_naive()
    yesterday = now - timedelta(hours=24)
    last_week = now - timedelta(days=7)

    # === Devices ===
    total_devices = (await db.execute(
        select(func.count()).where(Device.is_visible == True)
    )).scalar() or 0

    devices_online = (await db.execute(
        select(func.count()).where(
            Device.status == DeviceStatus.ONLINE, Device.is_visible == True
        )
    )).scalar() or 0

    devices_offline = (await db.execute(
        select(func.count()).where(
            Device.status == DeviceStatus.OFFLINE, Device.is_visible == True
        )
    )).scalar() or 0

    snmp_active = (await db.execute(
        select(func.count()).where(
            Device.snmp_enabled == True, Device.is_visible == True
        )
    )).scalar() or 0

    new_devices_24h = (await db.execute(
        select(func.count()).where(Device.first_seen >= yesterday)
    )).scalar() or 0

    # Device types breakdown
    type_query = await db.execute(
        select(Device.device_type, func.count())
        .where(Device.is_visible == True)
        .group_by(Device.device_type)
    )
    device_types = {
        row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1]
        for row in type_query
    }

    # === Scans ===
    active_scans = (await db.execute(
        select(func.count()).where(
            ScanJob.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING])
        )
    )).scalar() or 0

    scans_last_week = (await db.execute(
        select(func.count()).where(ScanJob.created_at >= last_week)
    )).scalar() or 0

    # === Vulnerabilities ===
    total_vulns = (await db.execute(
        select(func.count()).where(VulnerabilityFinding.is_resolved == False)
    )).scalar() or 0

    vuln_counts = {}
    for level in SeverityLevel:
        c = (await db.execute(
            select(func.count()).where(
                VulnerabilityFinding.severity == level,
                VulnerabilityFinding.is_resolved == False,
            )
        )).scalar() or 0
        vuln_counts[level.value] = c

    # === Alerts ===
    active_alerts = (await db.execute(
        select(func.count()).where(Alert.status == AlertStatus.ACTIVE)
    )).scalar() or 0

    critical_alerts = (await db.execute(
        select(func.count()).where(
            Alert.severity == "critical",
            Alert.status == AlertStatus.ACTIVE,
        )
    )).scalar() or 0

    muted_alerts = (await db.execute(
        select(func.count()).where(Alert.is_muted == True)
    )).scalar() or 0

    # === Agents ===
    total_agents = (await db.execute(
        select(func.count(AgentRegistration.id))
    )).scalar() or 0

    registered_agents = list((await db.execute(select(AgentRegistration))).scalars().all())
    active_agents = sum(1 for agent in registered_agents if agent_is_online(agent, now))
    offline_agents = sum(1 for agent in registered_agents if agent.is_active and not agent_is_online(agent, now))

    return {
        "devices": {
            "total": total_devices,
            "online": devices_online,
            "offline": devices_offline,
            "snmp_active": snmp_active,
            "snmp_inactive": total_devices - snmp_active,
            "new_last_24h": new_devices_24h,
            "by_type": device_types,
        },
        "scans": {
            "active": active_scans,
            "last_week": scans_last_week,
        },
        "vulnerabilities": {
            "total_open": total_vulns,
            "by_severity": vuln_counts,
        },
        "alerts": {
            "active": active_alerts,
            "critical": critical_alerts,
            "muted": muted_alerts,
        },
        "agents": {
            "total": total_agents,
            "active": active_agents,
            "offline": offline_agents,
        },
    }
