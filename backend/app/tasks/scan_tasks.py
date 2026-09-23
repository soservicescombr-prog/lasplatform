# netguard/backend/app/tasks/scan_tasks.py
"""
NetGuard - Celery tasks para scans de rede (Discovery, Vulnerability, Pentest).
"""

import asyncio
from uuid import UUID

from celery import states
from loguru import logger
from sqlalchemy import select, update

from app.tasks import celery_app
from app.utils.time import utcnow_naive
from app.utils.async_runner import run_async
from app.database import async_session
from app.models.scan import ScanJob, ScanStatus, ScanType
from app.services.schedule_service import calculate_next_run


class DiscoveryNotRunnable(Exception):
    """Sinaliza entrega duplicada ou job que já está em outro estado."""


async def _update_scan_status(scan_job_id: str, status: ScanStatus, **kwargs):
    """Atualiza status do scan job no banco."""
    async with async_session() as db:
        values = {"status": status, **kwargs}
        await db.execute(
            update(ScanJob)
            .where(ScanJob.id == UUID(scan_job_id))
            .values(**values)
        )
        await db.commit()


async def _update_discovery_progress(
    scan_job_id: str,
    progress: int,
    stage: str,
    message: str,
) -> bool:
    """Persiste progresso/heartbeat e retorna False quando o job foi cancelado."""
    async with async_session() as db:
        result = await db.execute(
            update(ScanJob)
            .where(
                ScanJob.id == UUID(scan_job_id),
                ScanJob.status == ScanStatus.RUNNING,
            )
            .values(
                progress=max(0, min(progress, 99)),
                results_summary={
                    "stage": stage,
                    "message": message,
                    "heartbeat_at": utcnow_naive().isoformat(),
                },
            )
        )
        await db.commit()
        return bool(result.rowcount)


async def _start_discovery(scan_job_id: str) -> None:
    """Move um discovery confirmado de pendente para execução."""
    from app.services.discovery_service import DiscoveryCancelled

    async with async_session() as db:
        result = await db.execute(
            update(ScanJob)
            .where(
                ScanJob.id == UUID(scan_job_id),
                ScanJob.status == ScanStatus.PENDING,
            )
            .values(
                status=ScanStatus.RUNNING,
                started_at=utcnow_naive(),
                progress=2,
                error_message=None,
                results_summary={
                    "stage": "starting",
                    "message": "Worker iniciou a execução",
                    "heartbeat_at": utcnow_naive().isoformat(),
                },
            )
        )
        await db.commit()
        if result.rowcount:
            return

        status_result = await db.execute(
            select(ScanJob.status).where(ScanJob.id == UUID(scan_job_id))
        )
        current_status = status_result.scalar_one_or_none()
        if current_status is None:
            raise LookupError(f"Scan job {scan_job_id} não encontrado no banco")
        if current_status == ScanStatus.CANCELLED:
            raise DiscoveryCancelled("Cancelamento solicitado pelo usuário")
        raise DiscoveryNotRunnable(
            f"Discovery ignorado porque o job está no estado {current_status.value}"
        )


async def _run_discovery(scan_job_id: str):
    """Executa o discovery em thread, mantendo updates no mesmo event loop."""
    from app.services.discovery_service import (
        DiscoveryCancelled,
        DiscoveryService,
        save_discovered_devices,
    )

    await _start_discovery(scan_job_id)
    job_data = await _get_scan_job(scan_job_id)
    if not job_data:
        raise LookupError(f"Scan job {scan_job_id} não encontrado")

    loop = asyncio.get_running_loop()

    def progress_callback(progress: int, stage: str, message: str) -> bool:
        future = asyncio.run_coroutine_threadsafe(
            _update_discovery_progress(scan_job_id, progress, stage, message),
            loop,
        )
        accepted = future.result(timeout=15)
        if accepted:
            logger.info(
                "Discovery {} progress: {}% [{}] {}",
                scan_job_id,
                progress,
                stage,
                message,
            )
        return accepted

    service = DiscoveryService()
    discovered = await asyncio.to_thread(
        service.run_discovery,
        job_data["target"],
        scan_job_id,
        job_data["options"],
        progress_callback,
    )
    if not await _update_discovery_progress(
        scan_job_id, 98, "saving", f"Salvando {len(discovered)} dispositivo(s)"
    ):
        raise DiscoveryCancelled("Discovery cancelado antes da persistência")
    return await save_discovered_devices(discovered, UUID(scan_job_id))


async def _get_scan_job(scan_job_id: str) -> dict:
    """Recupera dados do scan job."""
    async with async_session() as db:
        result = await db.execute(
            select(ScanJob).where(ScanJob.id == UUID(scan_job_id))
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        return {
            "id": str(job.id),
            "scan_type": job.scan_type.value,
            "target": job.target,
            "target_ports": job.target_ports,
            "options": job.options or {},
        }


async def _prepare_scheduled_discoveries() -> list[dict]:
    """Cria jobs pendentes para agendamentos vencidos de forma transacional."""
    now = utcnow_naive()
    prepared: list[dict] = []
    async with async_session() as db:
        result = await db.execute(
            select(ScanJob)
            .where(
                ScanJob.scan_type == ScanType.DISCOVERY,
                ScanJob.is_scheduled == True,
                ScanJob.next_run.is_not(None),
                ScanJob.next_run <= now,
            )
            .with_for_update(skip_locked=True)
        )
        templates = result.scalars().all()

        for template in templates:
            options = dict(template.options or {})
            schedule_config = options.get("schedule")
            if not isinstance(schedule_config, dict):
                logger.error("Disabling invalid discovery schedule {}", template.id)
                template.is_scheduled = False
                template.next_run = None
                continue

            template.next_run = calculate_next_run(schedule_config, after=now)
            execution_options = dict(options)
            execution_options["scheduled_from"] = str(template.id)
            execution = ScanJob(
                name=f"{template.name[:150]} · agendado {now:%Y-%m-%d %H:%M}",
                scan_type=ScanType.DISCOVERY,
                target=template.target,
                target_ports=template.target_ports,
                options=execution_options,
                is_scheduled=False,
                created_by=template.created_by,
                results_summary={
                    "stage": "queued",
                    "message": "Execução criada pelo agendamento",
                    "scheduled_from": str(template.id),
                },
            )
            db.add(execution)
            prepared.append({"execution": execution, "template_id": str(template.id)})

        await db.flush()
        payload = [
            {"job_id": str(item["execution"].id), "template_id": item["template_id"]}
            for item in prepared
        ]
        await db.commit()
        return payload


async def _store_scheduled_dispatch(scan_job_id: str, task_id: str) -> None:
    async with async_session() as db:
        await db.execute(
            update(ScanJob)
            .where(ScanJob.id == UUID(scan_job_id))
            .values(celery_task_id=task_id)
        )
        await db.commit()


@celery_app.task(name="netguard.dispatch_scheduled_scans", queue="scans")
def dispatch_scheduled_scans():
    """Publica discoveries cuja próxima execução já venceu."""
    jobs = run_async(_prepare_scheduled_discoveries())
    dispatched = 0
    failed = 0
    for job in jobs:
        try:
            task = celery_app.send_task(
                "netguard.run_discovery_scan",
                args=[job["job_id"]],
                queue="scans",
                routing_key="scans",
            )
            run_async(_store_scheduled_dispatch(job["job_id"], task.id))
            dispatched += 1
            logger.info(
                "Scheduled discovery {} dispatched from template {}",
                job["job_id"],
                job["template_id"],
            )
        except Exception as exc:
            failed += 1
            run_async(_update_scan_status(
                job["job_id"],
                ScanStatus.FAILED,
                error_message=f"Falha ao publicar execução agendada: {exc}"[:4000],
                completed_at=utcnow_naive(),
            ))
    return {"due": len(jobs), "dispatched": dispatched, "failed": failed}


@celery_app.task(bind=True, name="netguard.run_discovery_scan", queue="scans")
def run_discovery_scan(self, scan_job_id: str):
    """Task: Discovery scan na rede com nmap."""
    logger.info("Starting discovery scan task: {}", scan_job_id)

    try:
        result = run_async(_run_discovery(scan_job_id))

        logger.info("Discovery scan {} completed: {}", scan_job_id, result)
        return result

    except Exception as e:
        from app.services.discovery_service import DiscoveryCancelled

        if isinstance(e, DiscoveryCancelled):
            logger.info("Discovery scan {} cancelled", scan_job_id)
            return {"status": "cancelled"}
        if isinstance(e, DiscoveryNotRunnable):
            logger.warning("{}", e)
            return {"status": "ignored", "reason": str(e)}
        logger.error("Discovery scan {} failed: {}", scan_job_id, e)
        run_async(_update_scan_status(
            scan_job_id, ScanStatus.FAILED,
            error_message=str(e)[:4000],
            results_summary={
                "stage": "failed",
                "message": "Falha na execução do discovery",
                "heartbeat_at": utcnow_naive().isoformat(),
            },
            completed_at=utcnow_naive(),
        ))
        self.update_state(state=states.FAILURE, meta={"error": str(e)})
        raise


@celery_app.task(bind=True, name="netguard.run_vulnerability_scan", queue="scans")
def run_vulnerability_scan(self, scan_job_id: str):
    """Task: Scan de vulnerabilidades."""
    logger.info("Starting vulnerability scan: {}", scan_job_id)

    run_async(_update_scan_status(
        scan_job_id, ScanStatus.RUNNING,
        started_at=utcnow_naive(),
    ))

    try:
        job_data = run_async(_get_scan_job(scan_job_id))
        if not job_data:
            return

        from app.services.vulnerability_service import VulnerabilityService

        service = VulnerabilityService()
        result = service.run_scan(
            target=job_data["target"],
            ports=job_data.get("target_ports"),
            scan_job_id=scan_job_id,
            options=job_data.get("options", {}),
        )

        run_async(_update_scan_status(
            scan_job_id, ScanStatus.COMPLETED,
            completed_at=utcnow_naive(),
            progress=100,
            results_summary=result,
        ))
        return result

    except Exception as e:
        logger.error("Vulnerability scan {} failed: {}", scan_job_id, e)
        run_async(_update_scan_status(
            scan_job_id, ScanStatus.FAILED,
            error_message=str(e),
            completed_at=utcnow_naive(),
        ))
        raise


@celery_app.task(bind=True, name="netguard.run_pentest", queue="scans")
def run_pentest(self, scan_job_id: str):
    """Task: Pentest automatizado."""
    logger.info("Starting pentest: {}", scan_job_id)

    run_async(_update_scan_status(
        scan_job_id, ScanStatus.RUNNING,
        started_at=utcnow_naive(),
    ))

    try:
        job_data = run_async(_get_scan_job(scan_job_id))
        if not job_data:
            return

        from app.services.pentest_service import PentestService

        service = PentestService()
        result = service.run_pentest(
            target=job_data["target"],
            scan_job_id=scan_job_id,
            options=job_data.get("options", {}),
        )

        run_async(_update_scan_status(
            scan_job_id, ScanStatus.COMPLETED,
            completed_at=utcnow_naive(),
            progress=100,
            results_summary=result,
        ))
        return result

    except Exception as e:
        logger.error("Pentest {} failed: {}", scan_job_id, e)
        run_async(_update_scan_status(
            scan_job_id, ScanStatus.FAILED,
            error_message=str(e),
            completed_at=utcnow_naive(),
        ))
        raise
