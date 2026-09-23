"""Persistent log search, facets and log-derived metrics."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_operator_user
from app.config import get_settings
from app.database import get_db
from app.models.alert import AlertRule
from app.models.log import LogMetric, SyslogEvent
from app.models.metric import AgentMetric, DeviceMetric
from app.models.snmp import SNMPCollection
from app.models.user import User
from app.schemas.log import (
    LogEventListResponse,
    LogMetricCreate,
    LogMetricResponse,
    LogMetricUpdate,
)
from app.services.log_service import apply_log_filters, count_matching_logs, normalize_filters
from app.services.syslog_service import syslog_receiver
from app.utils.time import utcnow_naive

router = APIRouter()
settings = get_settings()


def _search_filters(**kwargs) -> dict:
    return normalize_filters(kwargs)


def _metric_response(metric: LogMetric, rule: AlertRule | None) -> LogMetricResponse:
    return LogMetricResponse(
        id=metric.id,
        name=metric.name,
        description=metric.description,
        filters=metric.filters or {},
        window_minutes=metric.window_minutes,
        threshold=metric.threshold,
        minimum_span_seconds=metric.minimum_span_seconds,
        threshold_operator=metric.threshold_operator,
        severity=metric.severity,
        is_active=metric.is_active,
        current_value=metric.current_value or 0,
        last_evaluated_at=metric.last_evaluated_at,
        last_triggered_at=metric.last_triggered_at,
        alert_rule_id=metric.alert_rule_id,
        cooldown_minutes=rule.cooldown_minutes if rule else 15,
        notify_email=rule.notify_email if rule else False,
        notify_webhook=rule.notify_webhook if rule else False,
        webhook_url=rule.webhook_url if rule else None,
        created_at=metric.created_at,
    )


@router.get("/events", response_model=LogEventListResponse)
async def search_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    q: str | None = None,
    match: str = Query("all", pattern="^(all|any)$"),
    severity: str | None = None,
    facility: str | None = None,
    host: str | None = None,
    source_ip: str | None = None,
    hostname: str | None = None,
    app_name: str | None = None,
    protocol: str | None = None,
    property_key: str | None = None,
    property_value: str | None = None,
    security_category: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = _search_filters(
        q=q, match=match, severity=severity, facility=facility, host=host,
        source_ip=source_ip, hostname=hostname, app_name=app_name,
        protocol=protocol, property_key=property_key, property_value=property_value,
        security_category=security_category, from_time=from_time, to_time=to_time,
    )
    query = apply_log_filters(select(SyslogEvent), filters)
    total_query = apply_log_filters(select(func.count(SyslogEvent.id)), filters)
    total = int((await db.execute(total_query)).scalar() or 0)
    result = await db.execute(
        query.order_by(desc(SyslogEvent.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return LogEventListResponse(
        items=result.scalars().all(), total=total, page=page, page_size=page_size
    )


@router.get("/stats")
async def log_stats(
    minutes: int = Query(1440, ge=1, le=10080),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = utcnow_naive() - timedelta(minutes=minutes)
    total = int((await db.execute(
        select(func.count(SyslogEvent.id)).where(SyslogEvent.received_at >= cutoff)
    )).scalar() or 0)

    async def grouped(column, limit=20):
        rows = (await db.execute(
            select(column, func.count(SyslogEvent.id))
            .where(SyslogEvent.received_at >= cutoff)
            .group_by(column)
            .order_by(desc(func.count(SyslogEvent.id)))
            .limit(limit)
        )).all()
        return {str(key or "unknown"): int(value) for key, value in rows}

    security_events = int((await db.execute(
        select(func.count(SyslogEvent.id)).where(
            SyslogEvent.received_at >= cutoff,
            SyslogEvent.security_category.is_not(None),
        )
    )).scalar() or 0)
    rate_5m = int((await db.execute(
        select(func.count(SyslogEvent.id)).where(
            SyslogEvent.received_at >= utcnow_naive() - timedelta(minutes=5)
        )
    )).scalar() or 0)
    return {
        "period_minutes": minutes,
        "total_messages": total,
        "rate_5m": rate_5m,
        "security_events": security_events,
        "by_severity": await grouped(SyslogEvent.severity),
        "by_source": await grouped(SyslogEvent.source_ip),
        "by_facility": await grouped(SyslogEvent.facility),
        "receiver": syslog_receiver.health(),
    }


@router.get("/facets")
async def log_facets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def values(column, limit=100):
        rows = (await db.execute(
            select(column).where(column.is_not(None)).distinct().order_by(column).limit(limit)
        )).scalars().all()
        return list(rows)

    return {
        "severities": await values(SyslogEvent.severity),
        "facilities": await values(SyslogEvent.facility),
        "hosts": await values(SyslogEvent.hostname),
        "sources": await values(SyslogEvent.source_ip),
        "applications": await values(SyslogEvent.app_name),
        "protocols": await values(SyslogEvent.protocol),
    }


@router.get("/receiver/health")
async def receiver_health(current_user: User = Depends(get_current_user)):
    health = syslog_receiver.health()
    health.update({
        "external_port": settings.SYSLOG_EXTERNAL_PORT,
        "port_mapping_required": settings.SYSLOG_EXTERNAL_PORT != health["port"],
    })
    return health


@router.get("/ingestion/health")
async def ingestion_health(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Database-backed proof of the three ingestion pipelines."""
    async def table_state(model, timestamp):
        count, latest = (await db.execute(select(func.count(model.id), func.max(timestamp)))).one()
        recent = int((await db.execute(select(func.count(model.id)).where(
            timestamp >= utcnow_naive() - timedelta(minutes=5)
        ))).scalar() or 0)
        return {"total": int(count or 0), "last_persisted_at": latest.isoformat() if latest else None, "last_5m": recent}

    return {
        "syslog": await table_state(SyslogEvent, SyslogEvent.received_at),
        "agent_metrics": await table_state(AgentMetric, AgentMetric.collected_at),
        "device_metrics": await table_state(DeviceMetric, DeviceMetric.collected_at),
        "snmp_collections": await table_state(SNMPCollection, SNMPCollection.collected_at),
        "receiver": syslog_receiver.health(),
        "checked_at": utcnow_naive().isoformat(),
    }


@router.post("/receiver/test")
async def test_receiver_persistence(
    db: AsyncSession = Depends(get_db), operator: User = Depends(get_operator_user),
):
    """Injects one synthetic event through the real parser/persistence path."""
    marker = f"netguard-ingestion-test-{utcnow_naive().strftime('%Y%m%d%H%M%S%f')}"
    await syslog_receiver.process_message(
        f"<134>1 {utcnow_naive().isoformat()}Z netguard selftest - - - {marker}".encode(),
        ("127.0.0.1", 514), "selftest",
    )
    event = await db.scalar(select(SyslogEvent).where(SyslogEvent.message == marker))
    if not event:
        raise HTTPException(status_code=500, detail="O receptor processou a mensagem, mas ela não foi localizada no banco")
    return {"status": "persisted", "event_id": str(event.id), "marker": marker}


@router.get("/metrics", response_model=list[LogMetricResponse])
async def list_log_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = (await db.execute(select(LogMetric).order_by(LogMetric.name))).scalars().all()
    rule_ids = [metric.alert_rule_id for metric in metrics if metric.alert_rule_id]
    rules = {}
    if rule_ids:
        found = (await db.execute(select(AlertRule).where(AlertRule.id.in_(rule_ids)))).scalars().all()
        rules = {rule.id: rule for rule in found}
    return [_metric_response(metric, rules.get(metric.alert_rule_id)) for metric in metrics]


@router.post("/metrics", response_model=LogMetricResponse, status_code=201)
async def create_log_metric(
    data: LogMetricCreate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    exists = (await db.execute(select(LogMetric.id).where(LogMetric.name == data.name))).scalar()
    if exists:
        raise HTTPException(status_code=409, detail="Já existe uma métrica com este nome")
    filters = normalize_filters(data.filters)
    rule = AlertRule(
        name=f"Logs: {data.name}",
        description=data.description,
        category="log_metric",
        severity=data.severity,
        is_active=data.is_active,
        condition_type="log_metric",
        condition_params={},
        threshold_value=float(data.threshold),
        threshold_operator=data.threshold_operator,
        notify_email=data.notify_email,
        notify_webhook=data.notify_webhook,
        webhook_url=data.webhook_url,
        cooldown_minutes=data.cooldown_minutes,
        created_by=operator.id,
    )
    db.add(rule)
    await db.flush()
    metric = LogMetric(
        name=data.name,
        description=data.description,
        filters=filters,
        window_minutes=data.window_minutes,
        threshold=data.threshold,
        minimum_span_seconds=data.minimum_span_seconds,
        threshold_operator=data.threshold_operator,
        severity=data.severity,
        is_active=data.is_active,
        alert_rule_id=rule.id,
        created_by=operator.id,
    )
    db.add(metric)
    await db.flush()
    rule.condition_params = {"metric_id": str(metric.id)}
    metric.current_value = await count_matching_logs(db, metric.filters, metric.window_minutes)
    metric.last_evaluated_at = utcnow_naive()
    await db.flush()
    return _metric_response(metric, rule)


@router.put("/metrics/{metric_id}", response_model=LogMetricResponse)
async def update_log_metric(
    metric_id: UUID,
    data: LogMetricUpdate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    metric = (await db.execute(select(LogMetric).where(LogMetric.id == metric_id))).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=404, detail="Métrica não encontrada")
    rule = None
    if metric.alert_rule_id:
        rule = (await db.execute(select(AlertRule).where(AlertRule.id == metric.alert_rule_id))).scalar_one_or_none()
    values = data.model_dump(exclude_unset=True)
    rule_fields = {"cooldown_minutes", "notify_email", "notify_webhook", "webhook_url"}
    for field, value in values.items():
        if field in rule_fields:
            if rule:
                setattr(rule, field, value)
        else:
            setattr(metric, field, normalize_filters(value) if field == "filters" else value)
    if rule:
        rule.name = f"Logs: {metric.name}"
        rule.description = metric.description
        rule.severity = metric.severity
        rule.is_active = metric.is_active
        rule.threshold_value = float(metric.threshold)
        rule.threshold_operator = metric.threshold_operator
    metric.current_value = await count_matching_logs(db, metric.filters, metric.window_minutes)
    metric.last_evaluated_at = utcnow_naive()
    await db.flush()
    return _metric_response(metric, rule)


@router.post("/metrics/{metric_id}/evaluate", response_model=LogMetricResponse)
async def evaluate_log_metric(
    metric_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    metric = (await db.execute(select(LogMetric).where(LogMetric.id == metric_id))).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=404, detail="Métrica não encontrada")
    rule = None
    if metric.alert_rule_id:
        rule = (await db.execute(select(AlertRule).where(AlertRule.id == metric.alert_rule_id))).scalar_one_or_none()
    metric.current_value = await count_matching_logs(db, metric.filters, metric.window_minutes)
    metric.last_evaluated_at = utcnow_naive()
    await db.flush()
    return _metric_response(metric, rule)


@router.delete("/metrics/{metric_id}", status_code=204)
async def delete_log_metric(
    metric_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    metric = (await db.execute(select(LogMetric).where(LogMetric.id == metric_id))).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=404, detail="Métrica não encontrada")
    rule_id = metric.alert_rule_id
    await db.delete(metric)
    await db.flush()
    if rule_id:
        rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
        if rule:
            await db.delete(rule)
