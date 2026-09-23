# netguard/backend/app/api/v1/endpoints/agents.py
"""
NetGuard - Endpoints para Agentes (registro, heartbeat, relatórios).
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, get_operator_user
from app.core.security import create_agent_token, decode_token
from app.models.user import User
from app.models.agent import AgentRegistration, AgentReport
from app.models.device import Device, DeviceStatus
from app.models.alert import Alert
from app.models.log import SyslogEvent
from app.models.metric import AgentMetric, AgentBaseline
from app.services.baseline_service import evaluate_agent_baselines
from app.services.syslog_service import SyslogMessage
from app.utils.time import utcnow_naive

from pydantic import BaseModel
from typing import Optional

router = APIRouter()

AGENT_DEFAULT_CONFIG = {
    "heartbeat_interval_seconds": 15,
    "metrics_interval_seconds": 15,
    "log_batch_size": 500,
    "log_paths": [],
}


def _effective_config(agent: AgentRegistration) -> dict:
    return {**AGENT_DEFAULT_CONFIG, **(agent.config or {})}


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def _store_metrics(db: AsyncSession, agent: AgentRegistration, metrics: dict | None):
    if not isinstance(metrics, dict) or not metrics:
        return
    boot_time = None
    if metrics.get("boot_time"):
        try:
            boot_time = datetime.fromisoformat(str(metrics["boot_time"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    gauges = {key: _number(metrics.get(key)) for key in (
        "cpu_usage", "memory_usage", "disk_usage", "load_1m", "load_5m", "load_15m",
    )}
    counters = {key: int(metrics.get(key) or 0) for key in (
        "network_bytes_sent", "network_bytes_recv", "network_packets_sent", "network_packets_recv",
        "disk_read_bytes", "disk_write_bytes", "process_count",
    )}
    latest = await db.scalar(select(AgentMetric).where(
        AgentMetric.agent_id == agent.id
    ).order_by(desc(AgentMetric.collected_at)).limit(1))
    rates = {"network_send_bps": None, "network_recv_bps": None, "disk_read_bps": None, "disk_write_bps": None}
    if latest:
        elapsed = max((utcnow_naive() - latest.collected_at).total_seconds(), 0)
        if elapsed:
            rates = {
                "network_send_bps": max(0, (counters["network_bytes_sent"] - (latest.network_bytes_sent or 0)) * 8 / elapsed),
                "network_recv_bps": max(0, (counters["network_bytes_recv"] - (latest.network_bytes_recv or 0)) * 8 / elapsed),
                "disk_read_bps": max(0, (counters["disk_read_bytes"] - (latest.disk_read_bytes or 0)) / elapsed),
                "disk_write_bps": max(0, (counters["disk_write_bytes"] - (latest.disk_write_bytes or 0)) / elapsed),
            }
    db.add(AgentMetric(agent_id=agent.id, boot_time=boot_time, details=metrics.get("details") or {}, **gauges, **counters, **rates))
    await evaluate_agent_baselines(db, agent, {**gauges, **rates})
    if agent.device_id:
        device = await db.scalar(select(Device).where(Device.id == agent.device_id))
        if device:
            device.cpu_usage, device.memory_usage, device.disk_usage = gauges["cpu_usage"], gauges["memory_usage"], gauges["disk_usage"]
            device.last_seen, device.status = utcnow_naive(), DeviceStatus.ONLINE


async def get_current_agent(
    authorization: str = Header(..., description="Bearer token do agente"),
    db: AsyncSession = Depends(get_db),
) -> AgentRegistration:
    """Valida o JWT do agente e confirma que o registro continua ativo."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        logger.warning("Agent authentication rejected: bearer token missing")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do agente ausente")

    payload = decode_token(token)
    if not payload or payload.get("type") != "agent" or not payload.get("sub"):
        logger.warning("Agent authentication rejected: invalid/expired JWT or SECRET_KEY mismatch")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do agente inválido")

    try:
        agent_id = UUID(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do agente inválido")

    agent = (await db.execute(
        select(AgentRegistration).where(AgentRegistration.id == agent_id)
    )).scalar_one_or_none()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not agent:
        logger.warning("Agent authentication rejected: registration {} not found", agent_id)
    elif not agent.is_active:
        logger.warning("Agent authentication rejected: registration {} inactive", agent_id)
    elif not (
            hmac.compare_digest(agent.agent_token, token_hash)
            or hmac.compare_digest(agent.agent_token, token)  # compatibilidade com registros antigos
    ):
        logger.warning("Agent authentication rejected: token mismatch for registration {}", agent_id)
    if not agent or not agent.is_active or not (
        agent and (hmac.compare_digest(agent.agent_token, token_hash) or hmac.compare_digest(agent.agent_token, token))
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agente não autorizado")
    return agent


class AgentRegisterRequest(BaseModel):
    hostname: str
    device_id: Optional[UUID] = None


class AgentRegisterResponse(BaseModel):
    agent_id: str
    agent_token: str
    message: str


@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(
    data: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Registra novo agente e retorna token."""
    import uuid as uuid_mod

    agent_id = uuid_mod.uuid4()
    token = create_agent_token(agent_id)

    agent = AgentRegistration(
        id=agent_id,
        device_id=data.device_id,
        agent_token=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        hostname=data.hostname,
        is_active=True,
    )
    db.add(agent)
    await db.flush()

    return AgentRegisterResponse(
        agent_id=str(agent_id),
        agent_token=token,
        message="Agente registrado. Use este token no config do agente.",
    )


@router.post("/heartbeat")
async def agent_heartbeat(
    data: dict,
    db: AsyncSession = Depends(get_db),
    agent: AgentRegistration = Depends(get_current_agent),
):
    """Recebe heartbeat do agente (autenticação via header)."""
    for field in ("hostname", "platform", "platform_version", "architecture", "agent_version", "python_version"):
        if data.get(field) is not None:
            setattr(agent, field, str(data[field])[:255])
    agent.last_heartbeat = utcnow_naive()
    await _store_metrics(db, agent, data.get("metrics"))
    await db.flush()
    return {"status": "ok", "agent_id": str(agent.id), "config": _effective_config(agent)}


@router.post("/report")
async def receive_agent_report(
    report: dict,
    db: AsyncSession = Depends(get_db),
    agent: AgentRegistration = Depends(get_current_agent),
):
    """Recebe relatório de scan do agente."""
    stored_report = AgentReport(
        agent_id=agent.id,
        report_type=str(report.get("report_type", "full_scan"))[:50],
        os_info=report.get("os_info"),
        installed_software=report.get("installed_software"),
        running_services=report.get("running_services"),
        open_ports=report.get("open_ports"),
        pending_updates=report.get("pending_updates"),
        vulnerabilities=report.get("vulnerabilities"),
        security_config=report.get("security_config"),
        runtime_versions=report.get("runtime_versions"),
        total_vulnerabilities=int(report.get("total_vulnerabilities", 0) or 0),
        critical_count=int(report.get("critical_count", 0) or 0),
        high_count=int(report.get("high_count", 0) or 0),
        medium_count=int(report.get("medium_count", 0) or 0),
        low_count=int(report.get("low_count", 0) or 0),
        raw_data=report,
    )
    db.add(stored_report)
    agent.last_report = utcnow_naive()
    agent.last_heartbeat = utcnow_naive()
    await _store_metrics(db, agent, report.get("metrics"))
    await db.flush()
    return {
        "status": "received",
        "report_id": str(stored_report.id),
        "vulnerabilities": stored_report.total_vulnerabilities,
    }


@router.get("")
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista agentes registrados."""
    query = select(AgentRegistration).order_by(AgentRegistration.created_at.desc())

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    agents = result.scalars().all()

    return {
        "items": [
            {
                "id": str(a.id),
                "hostname": a.hostname,
                "platform": a.platform,
                "platform_version": a.platform_version,
                "agent_version": a.agent_version,
                "is_active": a.is_active,
                "is_online": bool(a.is_active and a.last_heartbeat and (utcnow_naive() - a.last_heartbeat).total_seconds() <= 180),
                "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                "last_report": a.last_report.isoformat() if a.last_report else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in agents
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/logs")
async def receive_agent_logs(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    agent: AgentRegistration = Depends(get_current_agent),
):
    """Stores tailed host files in the central log pipeline."""
    entries = payload.get("entries") or []
    if not isinstance(entries, list) or len(entries) > 2000:
        raise HTTPException(status_code=422, detail="entries deve conter no máximo 2000 registros")
    stored = 0
    for item in entries:
        if not isinstance(item, dict) or not str(item.get("message", "")).strip():
            continue
        raw = str(item["message"])[:65535]
        parsed = SyslogMessage(raw, f"agent:{str(agent.id)[:36]}", None, "agent")
        parsed.hostname = agent.hostname
        parsed.app_name = Path(str(item.get("path") or "agent.log")).name[:255]
        parsed.properties.update({"agent_id": str(agent.id), "log_path": str(item.get("path") or "")[:1024]})
        parsed.match_security_pattern()
        db.add(SyslogEvent(
            received_at=parsed.received_at, event_at=parsed.event_at, source_ip=parsed.source_ip,
            protocol="agent", facility=parsed.facility_name, severity=parsed.severity_name,
            severity_num=parsed.severity, hostname=parsed.hostname, app_name=parsed.app_name,
            message=parsed.message, raw=parsed.raw, properties=parsed.properties,
            security_category=parsed.security_category, security_severity=parsed.security_severity,
        ))
        stored += 1
    agent.last_heartbeat = utcnow_naive()
    await db.flush()
    return {"status": "received", "stored": stored}


@router.put("/{agent_id}/config")
async def update_agent_config(
    agent_id: UUID, payload: dict, db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    agent = await db.scalar(select(AgentRegistration).where(AgentRegistration.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    paths = payload.get("log_paths", [])
    if not isinstance(paths, list) or len(paths) > 100 or any(not isinstance(path, str) for path in paths):
        raise HTTPException(status_code=422, detail="log_paths inválido")
    config = dict(agent.config or {})
    config.update({
        "log_paths": [path.strip() for path in paths if path.strip()],
        "metrics_interval_seconds": max(10, min(int(payload.get("metrics_interval_seconds", 15)), 3600)),
        "heartbeat_interval_seconds": max(10, min(int(payload.get("heartbeat_interval_seconds", 15)), 3600)),
        "log_batch_size": max(10, min(int(payload.get("log_batch_size", 500)), 2000)),
    })
    agent.config = config
    await db.flush()
    return {"status": "updated", "config": config}


@router.post("/{agent_id}/rotate-token", response_model=AgentRegisterResponse)
async def rotate_agent_token(
    agent_id: UUID, db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Revoga o token anterior e retorna um novo segredo uma única vez."""
    agent = await db.scalar(select(AgentRegistration).where(AgentRegistration.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    token = create_agent_token(agent.id)
    agent.agent_token = hashlib.sha256(token.encode("utf-8")).hexdigest()
    agent.is_active = True
    await db.flush()
    logger.info("Agent token rotated for {} by operator {}", agent_id, operator.id)
    return AgentRegisterResponse(
        agent_id=str(agent.id), agent_token=token,
        message="Token rotacionado. O token anterior foi revogado; atualize o arquivo do agente.",
    )


@router.get("/{agent_id}/details")
async def get_agent_details(
    agent_id: UUID,
    minutes: int | None = Query(None, ge=5, le=43200),
    hours: int | None = Query(None, ge=1, le=720),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    agent = await db.scalar(select(AgentRegistration).where(AgentRegistration.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    period_minutes = minutes if minutes is not None else ((hours or 24) * 60)
    cutoff = utcnow_naive() - timedelta(minutes=period_minutes)
    metrics = list((await db.execute(select(AgentMetric).where(
        AgentMetric.agent_id == agent_id, AgentMetric.collected_at >= cutoff,
    ).order_by(AgentMetric.collected_at).limit(3000))).scalars().all())
    reports = list((await db.execute(select(AgentReport).where(AgentReport.agent_id == agent_id).order_by(desc(AgentReport.created_at)).limit(20))).scalars().all())
    baselines = list((await db.execute(select(AgentBaseline).where(AgentBaseline.agent_id == agent_id))).scalars().all())
    logs = list((await db.execute(select(SyslogEvent).where(
        SyslogEvent.properties["agent_id"].astext == str(agent_id),
    ).order_by(desc(SyslogEvent.received_at)).limit(200))).scalars().all())
    alerts = list((await db.execute(select(Alert).where(
        Alert.details["agent_id"].astext == str(agent_id),
    ).order_by(desc(Alert.triggered_at)).limit(50))).scalars().all())
    latest = reports[0] if reports else None
    return {
        "agent": {"id": str(agent.id), "hostname": agent.hostname, "platform": agent.platform,
                  "platform_version": agent.platform_version, "architecture": agent.architecture,
                  "agent_version": agent.agent_version, "is_active": agent.is_active,
                  "is_online": bool(agent.is_active and agent.last_heartbeat and (utcnow_naive() - agent.last_heartbeat).total_seconds() <= 180),
                  "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
                  "last_report": agent.last_report.isoformat() if agent.last_report else None,
                  "config": _effective_config(agent)},
        "metrics": [{"timestamp": x.collected_at.isoformat(), "cpu_usage": x.cpu_usage,
                     "memory_usage": x.memory_usage, "disk_usage": x.disk_usage, "load_1m": x.load_1m,
                     "load_5m": x.load_5m, "load_15m": x.load_15m,
                     "network_bytes_sent": x.network_bytes_sent, "network_bytes_recv": x.network_bytes_recv,
                     "network_send_bps": x.network_send_bps, "network_recv_bps": x.network_recv_bps,
                     "disk_read_bytes": x.disk_read_bytes, "disk_write_bytes": x.disk_write_bytes,
                     "disk_read_bps": x.disk_read_bps, "disk_write_bps": x.disk_write_bps} for x in metrics],
        "baselines": [{"metric_name": x.metric_name, "status": x.status, "samples": x.sample_count,
                       "mean": x.mean, "stddev": x.stddev, "upper_bound": x.upper_bound,
                       "last_value": x.last_value, "last_exceeded_pct": x.last_exceeded_pct} for x in baselines],
        "latest_report": ({"created_at": latest.created_at.isoformat(), "os_info": latest.os_info,
                           "open_ports": latest.open_ports or [], "running_services": latest.running_services or [],
                           "pending_updates": latest.pending_updates or [], "vulnerabilities": latest.vulnerabilities or []} if latest else None),
        "logs": [{"id": str(x.id), "timestamp": x.received_at.isoformat(), "path": (x.properties or {}).get("log_path"),
                  "severity": x.severity, "message": x.message} for x in logs],
        "alerts": [{"id": str(x.id), "title": x.title, "severity": x.severity,
                    "status": x.status.value, "message": x.message, "triggered_at": x.triggered_at.isoformat()} for x in alerts],
    }


@router.delete("/{agent_id}", status_code=204)
async def deactivate_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Desativa um agente."""
    result = await db.execute(
        select(AgentRegistration).where(AgentRegistration.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    agent.is_active = False
    await db.flush()
