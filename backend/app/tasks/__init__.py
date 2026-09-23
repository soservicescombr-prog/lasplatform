# netguard/backend/app/tasks/__init__.py
"""
NetGuard - Celery tasks package.
"""

from celery import Celery
from kombu import Queue
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "netguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.scan_tasks",
        "app.tasks.snmp_tasks",
        "app.tasks.alert_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("scans"),
        Queue("snmp"),
        Queue("alerts"),
    ),
    task_routes={
        "netguard.run_discovery_scan": {"queue": "scans"},
        "netguard.run_vulnerability_scan": {"queue": "scans"},
        "netguard.run_pentest": {"queue": "scans"},
        "netguard.dispatch_scheduled_scans": {"queue": "scans"},
        "netguard.run_snmp_collection": {"queue": "snmp"},
        "netguard.run_bulk_snmp_collection": {"queue": "snmp"},
        "netguard.snmp_auto_detect": {"queue": "snmp"},
        "netguard.process_alert_rules": {"queue": "alerts"},
        "netguard.send_alert_notification": {"queue": "alerts"},
        "netguard.check_muted_alerts": {"queue": "alerts"},
        "netguard.cleanup_old_logs": {"queue": "alerts"},
        "netguard.monitor_availability": {"queue": "alerts"},
    },
)
