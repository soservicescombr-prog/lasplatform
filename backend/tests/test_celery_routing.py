"""Regressões do roteamento Celery do NetGuard."""

from app.tasks import celery_app


def test_default_queue_matches_worker_command():
    assert celery_app.conf.task_default_queue == "default"


def test_scan_tasks_are_routed_to_scans_queue():
    router = celery_app.amqp.router
    for task_name in (
        "netguard.run_discovery_scan",
        "netguard.run_vulnerability_scan",
        "netguard.run_pentest",
        "netguard.dispatch_scheduled_scans",
    ):
        route = router.route({}, task_name, args=(), kwargs={})
        assert route["queue"].name == "scans"


def test_all_declared_queues_match_operational_worker():
    queue_names = set(celery_app.amqp.queues.keys())
    assert queue_names == {"default", "scans", "snmp", "alerts"}
