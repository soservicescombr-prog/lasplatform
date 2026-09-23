"""Availability probes and offline alert lifecycle."""

import asyncio
import shutil
from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.models.agent import AgentRegistration
from app.models.alert import Alert, AlertStatus
from app.models.device import Device, DeviceStatus
from app.utils.time import utcnow_naive

settings = get_settings()


def agent_is_online(agent: AgentRegistration, now=None) -> bool:
    """Public compatibility helper used by dashboard and agent detail APIs."""
    if not agent.is_active or not agent.last_heartbeat:
        return False
    reference = now or utcnow_naive()
    return agent.last_heartbeat >= reference - timedelta(seconds=settings.AGENT_OFFLINE_SECONDS)


async def _active_alert(db, category, *, device_id=None, agent_id=None):
    query = select(Alert).where(Alert.category == category, Alert.status != AlertStatus.RESOLVED)
    if device_id:
        query = query.where(Alert.device_id == device_id)
    if agent_id:
        query = query.where(Alert.details["agent_id"].astext == str(agent_id))
    return (await db.execute(query)).scalars().first()


async def _set_alert(db, *, category, title, message, severity, device_id=None, details=None):
    details = details or {}
    existing = await _active_alert(db, category, device_id=device_id, agent_id=details.get("agent_id"))
    if existing:
        existing.message, existing.last_occurrence = message, utcnow_naive()
        existing.occurrence_count += 1
        return
    db.add(Alert(device_id=device_id, title=title, message=message, severity=severity,
                 category=category, details=details))


async def _resolve(db, category, *, device_id=None, agent_id=None):
    existing = await _active_alert(db, category, device_id=device_id, agent_id=agent_id)
    if existing:
        existing.status, existing.resolved_at = AlertStatus.RESOLVED, utcnow_naive()


async def resolve_agent_offline_alert(db, agent_id) -> int:
    """Resolve an agent-offline alert immediately after a heartbeat."""
    existing = await _active_alert(db, "agent_offline", agent_id=agent_id)
    if not existing:
        return 0
    existing.status, existing.resolved_at = AlertStatus.RESOLVED, utcnow_naive()
    existing.is_muted = False
    return 1


async def resolve_device_offline_alert(db, device_id) -> int:
    """Resolve a device-offline alert after a successful probe or collection."""
    existing = await _active_alert(db, "device_offline", device_id=device_id)
    if not existing:
        return 0
    existing.status, existing.resolved_at = AlertStatus.RESOLVED, utcnow_naive()
    existing.is_muted = False
    return 1


async def _probe(device):
    ping = shutil.which("ping")
    if not ping:
        return None
    try:
        process = await asyncio.create_subprocess_exec(ping, "-c", "1", "-W", "2", str(device.ip_address),
                                                       stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return await asyncio.wait_for(process.wait(), timeout=4) == 0
    except (OSError, asyncio.TimeoutError):
        return False


async def monitor_availability(db):
    now = utcnow_naive()
    agents = list((await db.execute(select(AgentRegistration).where(AgentRegistration.is_active == True))).scalars().all())
    for agent in agents:
        online = agent_is_online(agent, now)
        if online:
            await _resolve(db, "agent_offline", agent_id=agent.id)
        elif agent.last_heartbeat or (now - agent.created_at).total_seconds() >= settings.AGENT_OFFLINE_SECONDS:
            age = int((now - agent.last_heartbeat).total_seconds()) if agent.last_heartbeat else None
            await _set_alert(db, category="agent_offline", title=f"Agente offline: {agent.hostname or agent.id}",
                             message=f"Heartbeat ausente há {age} segundos." if age is not None else "Nenhum heartbeat recebido.",
                             severity="critical", device_id=agent.device_id,
                             details={"entity_type": "agent", "agent_id": str(agent.id), "heartbeat_age_seconds": age})

    devices = list((await db.execute(select(Device).where(Device.is_visible == True))).scalars().all())
    semaphore = asyncio.Semaphore(settings.AVAILABILITY_CONCURRENCY)
    async def limited(device):
        async with semaphore:
            return await _probe(device)
    results = await asyncio.gather(*(limited(device) for device in devices))
    for device, reachable in zip(devices, results):
        if reachable is None:
            continue
        fields = dict(device.custom_fields or {})
        failures = 0 if reachable else int(fields.get("availability_failures", 0) or 0) + 1
        fields.update({"availability_failures": failures, "last_availability_check": now.isoformat()})
        device.custom_fields = fields
        if reachable:
            device.status = DeviceStatus.ONLINE
            await _resolve(db, "device_offline", device_id=device.id)
        elif failures >= settings.DEVICE_OFFLINE_FAILURES:
            device.status = DeviceStatus.OFFLINE
            await _set_alert(db, category="device_offline", title=f"Dispositivo offline: {device.ip_address}",
                             message=f"Sem resposta em {failures} verificações ICMP consecutivas.", severity="high",
                             device_id=device.id, details={"entity_type": "device", "failure_count": failures})
    await db.commit()
    return {"agents": len(agents), "devices": len(devices)}
