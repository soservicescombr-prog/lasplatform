# netguard/backend/app/tasks/alert_tasks.py
"""
NetGuard - Celery tasks para processamento de alertas e notificações.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uuid import UUID

import httpx
from loguru import logger
from sqlalchemy import select, update, and_, delete

from app.tasks import celery_app
from app.config import get_settings
from app.database import async_session
from app.models.alert import Alert, AlertStatus, AlertRule
from app.models.device import Device, DeviceStatus
from app.models.scan import VulnerabilityFinding, SeverityLevel
from app.models.log import LogMetric
from app.models.log import SyslogEvent
from app.services.log_service import matching_log_stats, sustained_threshold_met
from app.utils.time import utcnow_naive
from app.utils.async_runner import run_async

settings = get_settings()


@celery_app.task(name="netguard.process_alert_rules")
def process_alert_rules():
    """Task periódica: avalia todas as regras de alerta ativas."""
    logger.info("Processing alert rules")

    async def _process():
        async with async_session() as db:
            result = await db.execute(
                select(AlertRule).where(AlertRule.is_active == True)
            )
            rules = result.scalars().all()
            alerts_created = 0

            for rule in rules:
                try:
                    triggered = await _evaluate_rule(db, rule)
                    alerts_created += triggered
                except Exception as e:
                    logger.error("Error evaluating rule {}: {}", rule.name, e)

            await db.commit()
            return alerts_created

    count = run_async(_process())
    logger.info("Alert rules processed: {} new alerts", count)
    return {"alerts_created": count}


async def _evaluate_rule(db, rule: AlertRule) -> int:
    """Avalia uma regra e cria alertas se necessário."""
    created = 0
    created_alerts: list[Alert] = []

    if rule.condition_type == "new_device":
        # Alert when new devices are discovered
        from datetime import timedelta
        threshold_minutes = rule.condition_params.get("minutes", 60)
        cutoff = utcnow_naive() - timedelta(minutes=threshold_minutes)
        result = await db.execute(
            select(Device).where(
                Device.first_seen >= cutoff,
                Device.is_visible == True,
            )
        )
        new_devices = result.scalars().all()
        for device in new_devices:
            existing = await db.execute(
                select(Alert).where(
                    Alert.device_id == device.id,
                    Alert.category == "new_device",
                    Alert.status != AlertStatus.RESOLVED,
                )
            )
            if not existing.scalar_one_or_none():
                alert = Alert(
                    device_id=device.id,
                    rule_id=rule.id,
                    title=f"Novo dispositivo detectado: {device.ip_address}",
                    message=f"Hostname: {device.hostname or 'N/A'}, Tipo: {device.device_type.value}",
                    severity=rule.severity,
                    category="new_device",
                )
                db.add(alert)
                created_alerts.append(alert)
                created += 1

    elif rule.condition_type == "device_offline":
        # Alert when devices go offline
        result = await db.execute(
            select(Device).where(
                Device.status == DeviceStatus.OFFLINE,
                Device.is_visible == True,
            )
        )
        offline_devices = result.scalars().all()
        for device in offline_devices:
            existing = await db.execute(
                select(Alert).where(
                    Alert.device_id == device.id,
                    Alert.category == "device_offline",
                    Alert.status != AlertStatus.RESOLVED,
                )
            )
            existing_alert = existing.scalar_one_or_none()
            if existing_alert:
                existing_alert.occurrence_count += 1
                existing_alert.last_occurrence = utcnow_naive()
            else:
                alert = Alert(
                    device_id=device.id,
                    rule_id=rule.id,
                    title=f"Dispositivo offline: {device.ip_address}",
                    message=f"Hostname: {device.hostname or 'N/A'}",
                    severity=rule.severity,
                    category="device_offline",
                )
                db.add(alert)
                created_alerts.append(alert)
                created += 1

    elif rule.condition_type == "critical_vulnerability":
        # Alert for critical/high vulnerabilities
        min_severity = rule.condition_params.get("min_severity", "high")
        severities = [SeverityLevel.CRITICAL]
        if min_severity in ("high", "medium"):
            severities.append(SeverityLevel.HIGH)
        if min_severity == "medium":
            severities.append(SeverityLevel.MEDIUM)

        result = await db.execute(
            select(VulnerabilityFinding).where(
                VulnerabilityFinding.severity.in_(severities),
                VulnerabilityFinding.is_resolved == False,
                VulnerabilityFinding.is_false_positive == False,
            )
        )
        vulns = result.scalars().all()
        for vuln in vulns:
            existing = await db.execute(
                select(Alert).where(
                    Alert.device_id == vuln.device_id,
                    Alert.category == "vulnerability",
                    Alert.title == vuln.title,
                    Alert.status != AlertStatus.RESOLVED,
                )
            )
            if not existing.scalar_one_or_none():
                alert = Alert(
                    device_id=vuln.device_id,
                    rule_id=rule.id,
                    title=f"Vulnerabilidade {vuln.severity.value}: {vuln.title}",
                    message=vuln.description,
                    severity=vuln.severity.value,
                    category="vulnerability",
                    details={"cve_id": vuln.cve_id, "port": vuln.port},
                )
                db.add(alert)
                created_alerts.append(alert)
                created += 1

    elif rule.condition_type == "interface_errors":
        # Alert for high interface error rates
        from app.models.snmp import SNMPInterface
        threshold = rule.threshold_value or 100
        result = await db.execute(
            select(SNMPInterface).where(
                (SNMPInterface.if_in_errors > threshold) |
                (SNMPInterface.if_out_errors > threshold)
            )
        )
        interfaces = result.scalars().all()
        for iface in interfaces:
            existing = await db.execute(
                select(Alert).where(
                    Alert.device_id == iface.device_id,
                    Alert.category == "interface_errors",
                    Alert.status != AlertStatus.RESOLVED,
                )
            )
            if not existing.scalar_one_or_none():
                alert = Alert(
                    device_id=iface.device_id,
                    rule_id=rule.id,
                    title=f"Erros na interface {iface.if_name or iface.if_descr}",
                    message=f"In errors: {iface.if_in_errors}, Out errors: {iface.if_out_errors}",
                    severity=rule.severity,
                    category="interface_errors",
                )
                db.add(alert)
                created_alerts.append(alert)
                created += 1

    elif rule.condition_type == "log_metric":
        metric_id = rule.condition_params.get("metric_id")
        if not metric_id:
            return 0
        result = await db.execute(select(LogMetric).where(LogMetric.id == UUID(metric_id)))
        metric = result.scalar_one_or_none()
        if not metric or not metric.is_active:
            return 0

        now = utcnow_naive()
        log_stats = await matching_log_stats(db, metric.filters or {}, metric.window_minutes)
        value = log_stats["count"]
        metric.current_value = value
        metric.last_evaluated_at = now
        triggered = sustained_threshold_met(
            value, metric.threshold_operator, metric.threshold,
            log_stats["span_seconds"], metric.minimum_span_seconds,
        )
        existing = (await db.execute(
            select(Alert).where(
                Alert.rule_id == rule.id,
                Alert.category == "log_metric",
                Alert.status != AlertStatus.RESOLVED,
            ).order_by(Alert.triggered_at.desc())
        )).scalars().first()

        if triggered and existing:
            existing.occurrence_count += 1
            existing.last_occurrence = now
            existing.message = (
                f"{value} ocorrência(s) nos últimos {metric.window_minutes} minuto(s); "
                f"condição {metric.threshold_operator} {metric.threshold}."
            )
            existing.details = {
                "metric_id": str(metric.id),
                "metric_name": metric.name,
                "current_value": value,
                "window_minutes": metric.window_minutes,
                "threshold": metric.threshold,
                "operator": metric.threshold_operator,
                "filters": metric.filters,
                "span_seconds": log_stats["span_seconds"],
                "minimum_span_seconds": metric.minimum_span_seconds,
            }
        elif triggered:
            from datetime import timedelta
            cooldown_ok = (
                not metric.last_triggered_at
                or metric.last_triggered_at <= now - timedelta(minutes=rule.cooldown_minutes or 15)
            )
            if cooldown_ok:
                alert = Alert(
                    rule_id=rule.id,
                    title=f"Métrica de logs: {metric.name}",
                    message=(
                        f"{value} ocorrência(s) nos últimos {metric.window_minutes} minuto(s); "
                        f"condição {metric.threshold_operator} {metric.threshold}."
                    ),
                    severity=metric.severity,
                    category="log_metric",
                    details={
                        "metric_id": str(metric.id),
                        "metric_name": metric.name,
                        "current_value": value,
                        "window_minutes": metric.window_minutes,
                        "threshold": metric.threshold,
                        "operator": metric.threshold_operator,
                        "filters": metric.filters,
                        "span_seconds": log_stats["span_seconds"],
                        "minimum_span_seconds": metric.minimum_span_seconds,
                    },
                )
                db.add(alert)
                created_alerts.append(alert)
                metric.last_triggered_at = now
                created += 1
        elif existing:
            existing.status = AlertStatus.RESOLVED
            existing.resolved_at = now

    # Trigger notifications for new alerts
    if created > 0 and (rule.notify_email or rule.notify_webhook):
        await db.flush()
        for alert in created_alerts:
            celery_app.send_task(
                "netguard.send_alert_notification",
                args=[str(alert.id)],
                queue="alerts",
            )

    return created


@celery_app.task(name="netguard.send_alert_notification")
def send_alert_notification(alert_id: str):
    """Task: Envia notificação de alerta (email/webhook)."""
    logger.info("Sending notification for alert {}", alert_id)

    async def _send():
        async with async_session() as db:
            result = await db.execute(
                select(Alert).where(Alert.id == UUID(alert_id))
            )
            alert = result.scalar_one_or_none()
            if not alert or alert.notification_sent:
                return

            # Email notification
            if alert.rule and alert.rule.notify_email and settings.SMTP_HOST:
                try:
                    _send_email(
                        subject=f"[NetGuard] {alert.severity.upper()}: {alert.title}",
                        body=f"Alerta: {alert.title}\n\nSeveridade: {alert.severity}\nCategoria: {alert.category}\n\n{alert.message or ''}\n\nTriggered: {alert.triggered_at}",
                    )
                except Exception as e:
                    logger.error("Email notification failed: {}", e)

            # Webhook notification
            if alert.rule and alert.rule.notify_webhook and alert.rule.webhook_url:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(alert.rule.webhook_url, json={
                            "event": "alert",
                            "severity": alert.severity,
                            "title": alert.title,
                            "message": alert.message,
                            "category": alert.category,
                            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                        })
                except Exception as e:
                    logger.error("Webhook notification failed: {}", e)

            alert.notification_sent = True
            await db.commit()

    run_async(_send())


def _send_email(subject: str, body: str):
    """Envia email via SMTP."""
    if not settings.SMTP_HOST:
        return

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = settings.SMTP_FROM_EMAIL  # Send to self / admin
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


@celery_app.task(name="netguard.check_muted_alerts")
def check_muted_alerts():
    """Task periódica: desmuta alertas cujo timer expirou."""
    logger.info("Checking muted alerts")

    async def _check():
        async with async_session() as db:
            now = utcnow_naive()
            result = await db.execute(
                select(Alert).where(
                    Alert.is_muted == True,
                    Alert.muted_until != None,
                    Alert.muted_until <= now,
                )
            )
            expired = result.scalars().all()
            count = 0
            for alert in expired:
                alert.is_muted = False
                alert.muted_until = None
                alert.status = AlertStatus.ACTIVE
                count += 1
            await db.commit()
            return count

    count = run_async(_check())
    if count > 0:
        logger.info("Unmuted {} expired alerts", count)
    return {"unmuted": count}


@celery_app.task(name="netguard.cleanup_old_logs")
def cleanup_old_logs():
    """Remove eventos além da retenção configurada."""
    from datetime import timedelta

    async def _cleanup():
        cutoff = utcnow_naive() - timedelta(days=max(settings.SYSLOG_RETENTION_DAYS, 1))
        async with async_session() as db:
            result = await db.execute(delete(SyslogEvent).where(SyslogEvent.received_at < cutoff))
            await db.commit()
            return result.rowcount or 0

    deleted = run_async(_cleanup())
    logger.info("Old syslog cleanup removed {} event(s)", deleted)
    return {"deleted": deleted}


# === Celery Beat schedule ===
@celery_app.task(name="netguard.monitor_availability", queue="alerts")
def monitor_availability_task():
    from app.services.availability_service import monitor_availability

    async def _run():
        async with async_session() as db:
            return await monitor_availability(db)

    return run_async(_run())


celery_app.conf.beat_schedule = {
    "dispatch-scheduled-scans-1m": {
        "task": "netguard.dispatch_scheduled_scans",
        "schedule": 60.0,
    },
    "process-alert-rules-1m": {
        "task": "netguard.process_alert_rules",
        "schedule": 60.0,
    },
    "check-muted-alerts-1m": {
        "task": "netguard.check_muted_alerts",
        "schedule": 60.0,  # Every minute
    },
    "monitor-availability-1m": {
        "task": "netguard.monitor_availability",
        "schedule": 60.0,
    },
    "cleanup-old-logs-daily": {
        "task": "netguard.cleanup_old_logs",
        "schedule": 86400.0,
    },
    "snmp-auto-detect-30m": {
        "task": "netguard.snmp_auto_detect",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "bulk-snmp-collection-5m": {
        "task": "netguard.run_bulk_snmp_collection",
        "schedule": 300.0,  # Every 5 minutes
    },
}
