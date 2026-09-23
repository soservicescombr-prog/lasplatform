# netguard/backend/app/api/v1/endpoints/alerts.py
"""
NetGuard - Endpoints de Alertas e Regras de Alerta.
"""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, get_operator_user, get_admin_user
from app.models.user import User
from app.utils.time import utcnow_naive
from app.models.alert import Alert, AlertStatus, AlertRule
from app.schemas.alert import (
    AlertResponse, AlertListResponse, AlertSummary,
    AlertMuteRequest, AlertAcknowledgeRequest,
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
)

router = APIRouter()


# === Alerts ===

@router.get("", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    severity: str = Query(None),
    device_id: UUID = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista alertas com filtros e paginação."""
    query = select(Alert)

    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if device_id:
        query = query.where(Alert.device_id == device_id)
    if category:
        query = query.where(Alert.category == category)

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    query = (
        query.order_by(desc(Alert.triggered_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertListResponse(
        items=alerts, total=total, page=page, page_size=page_size
    )


@router.get("/summary", response_model=AlertSummary)
async def alert_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumo dos alertas ativos."""
    active = (await db.execute(
        select(func.count()).where(Alert.status == AlertStatus.ACTIVE)
    )).scalar()

    sev_counts = {}
    for sev in ["critical", "high", "medium", "low"]:
        c = (await db.execute(
            select(func.count()).where(
                Alert.severity == sev,
                Alert.status == AlertStatus.ACTIVE,
            )
        )).scalar()
        sev_counts[sev] = c

    muted = (await db.execute(
        select(func.count()).where(Alert.is_muted == True)
    )).scalar()
    acked = (await db.execute(
        select(func.count()).where(Alert.status == AlertStatus.ACKNOWLEDGED)
    )).scalar()
    device_offline = (await db.execute(select(func.count()).where(
        Alert.category == "device_offline",
        Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.MUTED]),
    ))).scalar()
    agent_offline = (await db.execute(select(func.count()).where(
        Alert.category == "agent_offline",
        Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.MUTED]),
    ))).scalar()

    return AlertSummary(
        total_active=active,
        critical=sev_counts.get("critical", 0),
        high=sev_counts.get("high", 0),
        medium=sev_counts.get("medium", 0),
        low=sev_counts.get("low", 0),
        muted=muted,
        acknowledged=acked,
        device_offline=device_offline,
        agent_offline=agent_offline,
    )


@router.post("/{alert_id}/mute")
async def mute_alert(
    alert_id: UUID,
    data: AlertMuteRequest,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Muta um alerta (temporário ou indefinido)."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.is_muted = True
    alert.status = AlertStatus.MUTED
    alert.muted_by = operator.id
    alert.muted_reason = data.reason

    if data.duration_minutes:
        alert.muted_until = utcnow_naive() + timedelta(
            minutes=data.duration_minutes
        )

    await db.flush()
    return {"message": "Alerta mutado"}


@router.post("/{alert_id}/unmute")
async def unmute_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Desmuta um alerta."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.is_muted = False
    alert.muted_until = None
    alert.status = AlertStatus.ACTIVE
    await db.flush()
    return {"message": "Alerta desmutado"}


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    data: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Reconhece um alerta."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = operator.id
    alert.acknowledged_at = utcnow_naive()
    await db.flush()
    return {"message": "Alerta reconhecido"}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Resolve um alerta."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.status = AlertStatus.RESOLVED
    alert.is_muted = False
    alert.resolved_by = operator.id
    alert.resolved_at = utcnow_naive()
    await db.flush()
    return {"message": "Alerta resolvido"}


# === Alert Rules ===

@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista regras de alerta."""
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    return result.scalars().all()


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Cria nova regra de alerta."""
    rule = AlertRule(
        **data.model_dump(),
        created_by=admin.id,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: UUID,
    data: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Atualiza regra de alerta."""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra não encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Remove regra de alerta."""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    await db.delete(rule)
    await db.flush()
