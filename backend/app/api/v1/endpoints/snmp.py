# netguard/backend/app/api/v1/endpoints/snmp.py
"""
NetGuard - Endpoints SNMP: Communities CRUD, coleta e interfaces.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, get_operator_user, get_admin_user
from app.models.user import User
from app.models.device import Device
from app.models.snmp import SNMPCommunity, SNMPInterface, SNMPCollection
from app.schemas.snmp import (
    SNMPCommunityCreate, SNMPCommunityUpdate, SNMPCommunityResponse,
    SNMPInterfaceResponse, SNMPCollectRequest,
)

router = APIRouter()


# === Communities ===

@router.get("/communities", response_model=list[SNMPCommunityResponse])
async def list_communities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SNMPCommunity).order_by(SNMPCommunity.name)
    )
    return result.scalars().all()


@router.post("/communities", response_model=SNMPCommunityResponse, status_code=201)
async def create_community(
    data: SNMPCommunityCreate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    community = SNMPCommunity(**data.model_dump())
    db.add(community)
    await db.flush()
    await db.refresh(community)
    return community


@router.put("/communities/{community_id}", response_model=SNMPCommunityResponse)
async def update_community(
    community_id: UUID,
    data: SNMPCommunityUpdate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    result = await db.execute(
        select(SNMPCommunity).where(SNMPCommunity.id == community_id)
    )
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(status_code=404, detail="Community não encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(community, field, value)

    await db.flush()
    await db.refresh(community)
    return community


@router.delete("/communities/{community_id}", status_code=204)
async def delete_community(
    community_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(SNMPCommunity).where(SNMPCommunity.id == community_id)
    )
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(status_code=404, detail="Community não encontrada")
    await db.delete(community)
    await db.flush()


# === Collection ===

@router.post("/collect")
async def trigger_snmp_collection(
    data: SNMPCollectRequest,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Dispara coleta SNMP para um dispositivo."""
    device = (await db.execute(
        select(Device).where(Device.id == data.device_id)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    community_string = "public"
    if data.community_id:
        comm = (await db.execute(
            select(SNMPCommunity).where(SNMPCommunity.id == data.community_id)
        )).scalar_one_or_none()
        if comm:
            community_string = comm.community_string

    # Dispatch Celery task
    from app.tasks.snmp_tasks import run_snmp_collection
    task = run_snmp_collection.delay(str(data.device_id), community_string, str(data.community_id) if data.community_id else None)

    return {"message": "Coleta SNMP iniciada", "task_id": task.id}


# === Interfaces ===

@router.get("/interfaces/{device_id}", response_model=list[SNMPInterfaceResponse])
async def get_device_interfaces(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna interfaces SNMP de um dispositivo."""
    result = await db.execute(
        select(SNMPInterface)
        .where(SNMPInterface.device_id == device_id)
        .order_by(SNMPInterface.if_index)
    )
    return result.scalars().all()


@router.get("/history/{device_id}")
async def get_collection_history(
    device_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna histórico de coletas SNMP de um dispositivo."""
    result = await db.execute(
        select(SNMPCollection)
        .where(SNMPCollection.device_id == device_id)
        .order_by(SNMPCollection.collected_at.desc())
        .limit(limit)
    )
    collections = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "status": c.status,
            "duration_ms": c.duration_ms,
            "collected_at": c.collected_at.isoformat() if c.collected_at else None,
            "collection_data": c.collection_data,
        }
        for c in collections
    ]
