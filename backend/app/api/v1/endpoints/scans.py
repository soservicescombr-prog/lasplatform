# netguard/backend/app/api/v1/endpoints/scans.py
"""
NetGuard - Endpoints de Scan Jobs.
Implementação dos services de scan nos módulos 2, 4 e 6.
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.core.deps import get_current_user, get_operator_user
from app.models.user import User
from app.models.scan import ScanJob, ScanStatus, ScanType, VulnerabilityFinding
from app.utils.time import utcnow_naive
from app.services.schedule_service import calculate_next_run, schedule_expression
from app.schemas.scan import (
    ScanJobCreate, ScanJobResponse, ScanJobListResponse,
    VulnerabilityResponse, VulnerabilityListResponse, VulnerabilitySummary,
)

router = APIRouter()
settings = get_settings()


# === Scan Jobs ===

@router.post("", response_model=ScanJobResponse, status_code=201)
async def create_scan(
    data: ScanJobCreate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Cria e inicia um novo scan job."""
    options = dict(data.options or {})
    next_run = None
    schedule_cron = None
    if data.is_scheduled:
        schedule_config = {
            "frequency": data.schedule_frequency,
            "time": data.schedule_time,
            "days": sorted(set(data.schedule_days)),
            "day_of_month": data.schedule_day_of_month,
            "timezone": settings.SCHEDULE_TIMEZONE,
        }
        options["schedule"] = schedule_config
        next_run = calculate_next_run(schedule_config)
        schedule_cron = schedule_expression(schedule_config)

    scan = ScanJob(
        name=data.name,
        scan_type=ScanType(data.scan_type),
        target=data.target,
        target_ports=data.target_ports,
        options=options,
        is_scheduled=data.is_scheduled,
        schedule_cron=schedule_cron,
        next_run=next_run,
        created_by=operator.id,
        results_summary={
            "stage": "queued",
            "message": "Solicitação aguardando envio para a fila de execução",
        },
    )
    db.add(scan)
    # O job precisa estar confirmado no PostgreSQL antes da publicação. Caso
    # contrário, um worker rápido pode receber a mensagem e não enxergar a
    # linha ainda não commitada, interpretando o job como cancelado.
    await db.commit()
    await db.refresh(scan)

    # Dispatch appropriate Celery task based on scan type
    task_map = {
        "discovery": "netguard.run_discovery_scan",
        "port_scan": "netguard.run_discovery_scan",
        "vulnerability": "netguard.run_vulnerability_scan",
        "pentest": "netguard.run_pentest",
        "full": "netguard.run_discovery_scan",
    }
    task_name = task_map.get(data.scan_type)
    if task_name:
        try:
            from app.tasks import celery_app as celery
            # A fila precisa ser explícita: send_task() não usa os metadados do
            # decorator da task e, sem roteamento, publicaria na fila "celery".
            task = celery.send_task(
                task_name,
                args=[str(scan.id)],
                queue="scans",
                routing_key="scans",
            )
            scan.celery_task_id = task.id
            # Atualiza somente o identificador da task. O worker pode já ter
            # alterado status/progresso e esses campos não devem ser sobrescritos.
            await db.commit()
            await db.refresh(scan)
        except Exception as exc:
            scan.status = ScanStatus.FAILED
            scan.error_message = f"Falha ao enviar scan para o executor: {exc}"
            scan.results_summary = {"stage": "failed", "message": "Fila indisponível"}
            await db.commit()
            raise HTTPException(status_code=503, detail=scan.error_message)

    return scan


@router.post("/{scan_id}/schedule/disable")
async def disable_scan_schedule(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Desativa futuras execuções sem cancelar a execução atual."""
    result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan não encontrado")
    if not scan.is_scheduled:
        raise HTTPException(status_code=400, detail="Discovery não possui agendamento ativo")

    scan.is_scheduled = False
    scan.next_run = None
    await db.flush()
    return {"message": "Agendamento desativado"}


@router.get("", response_model=ScanJobListResponse)
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scan_type: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista scan jobs com filtros."""
    query = select(ScanJob)

    if scan_type:
        query = query.where(ScanJob.scan_type == scan_type)
    if status:
        query = query.where(ScanJob.status == status)

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    query = (
        query.order_by(desc(ScanJob.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    scans = result.scalars().all()

    return ScanJobListResponse(
        items=scans, total=total, page=page, page_size=page_size
    )


@router.get("/executor/health")
async def executor_health(
    current_user: User = Depends(get_current_user),
):
    """Informa se há workers Celery respondendo e aptos a executar scans."""
    from app.tasks import celery_app as celery

    try:
        inspector = celery.control.inspect(timeout=1.5)
        active_queues = await asyncio.to_thread(inspector.active_queues)
    except Exception as exc:
        return {
            "status": "offline",
            "workers": [],
            "message": f"Executor indisponível: {exc}",
        }
    subscriptions = {}
    for worker, queues in (active_queues or {}).items():
        subscriptions[worker] = sorted(
            queue.get("name") for queue in (queues or []) if queue.get("name")
        )
    workers = sorted(
        worker for worker, queues in subscriptions.items() if "scans" in queues
    )
    return {
        "status": "online" if workers else "offline",
        "workers": workers,
        "subscriptions": subscriptions,
        "message": (
            f"{len(workers)} worker(s) apto(s) para a fila scans"
            if workers
            else "Nenhum worker está consumindo a fila scans"
        ),
    }


@router.get("/{scan_id}", response_model=ScanJobResponse)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes de um scan job."""
    result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan não encontrado")
    return scan


@router.post("/{scan_id}/cancel")
async def cancel_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Cancela um scan em execução."""
    result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan não encontrado")

    if scan.status not in (ScanStatus.PENDING, ScanStatus.RUNNING):
        raise HTTPException(status_code=400, detail="Scan não pode ser cancelado")

    scan.status = ScanStatus.CANCELLED
    scan.completed_at = utcnow_naive()
    scan.results_summary = {
        "stage": "cancelled",
        "message": "Cancelamento solicitado pelo usuário",
        "heartbeat_at": utcnow_naive().isoformat(),
    }
    if scan.celery_task_id:
        from app.tasks import celery_app as celery
        celery.control.revoke(scan.celery_task_id, terminate=False)
    await db.flush()

    return {"message": "Scan cancelado"}


# === Vulnerabilities ===

@router.get("/vulnerabilities/all", response_model=VulnerabilityListResponse)
async def list_vulnerabilities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    severity: str = Query(None),
    device_id: UUID = Query(None),
    is_resolved: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todas as vulnerabilidades encontradas."""
    query = select(VulnerabilityFinding)

    if severity:
        query = query.where(VulnerabilityFinding.severity == severity)
    if device_id:
        query = query.where(VulnerabilityFinding.device_id == device_id)
    if is_resolved is not None:
        query = query.where(VulnerabilityFinding.is_resolved == is_resolved)

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    # By severity
    sev_query = await db.execute(
        select(VulnerabilityFinding.severity, func.count())
        .where(VulnerabilityFinding.is_resolved == False)
        .group_by(VulnerabilityFinding.severity)
    )
    by_severity = {
        row[0].value if hasattr(row[0], 'value') else row[0]: row[1]
        for row in sev_query
    }

    query = (
        query.order_by(desc(VulnerabilityFinding.last_detected))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return VulnerabilityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        by_severity=by_severity,
    )


@router.get("/vulnerabilities/summary", response_model=VulnerabilitySummary)
async def vulnerability_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumo de vulnerabilidades."""
    from app.models.scan import SeverityLevel

    total = (await db.execute(
        select(func.count(VulnerabilityFinding.id))
    )).scalar()

    counts = {}
    for level in SeverityLevel:
        c = (await db.execute(
            select(func.count()).where(
                VulnerabilityFinding.severity == level,
                VulnerabilityFinding.is_resolved == False,
            )
        )).scalar()
        counts[level.value] = c

    resolved = (await db.execute(
        select(func.count()).where(VulnerabilityFinding.is_resolved == True)
    )).scalar()
    false_pos = (await db.execute(
        select(func.count()).where(VulnerabilityFinding.is_false_positive == True)
    )).scalar()

    return VulnerabilitySummary(
        total=total,
        critical=counts.get("critical", 0),
        high=counts.get("high", 0),
        medium=counts.get("medium", 0),
        low=counts.get("low", 0),
        info=counts.get("info", 0),
        resolved=resolved,
        false_positives=false_pos,
    )
