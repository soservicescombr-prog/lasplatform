# netguard/backend/app/api/v1/endpoints/devices.py
"""
NetGuard - Endpoints de Dispositivos.
Implementação completa no Módulo 2 (Network Discovery).
"""

from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, get_operator_user
from app.models.user import User
from app.models.device import Device, DeviceStatus, DeviceType
from app.models.snmp import SNMPCollection, SNMPInterface
from app.models.metric import DeviceMetric
from app.models.alert import Alert
from app.models.log import SyslogEvent
from app.utils.time import utcnow_naive
from app.schemas.device import (
    DeviceResponse, DeviceListResponse, DeviceUpdate, DeviceSummary,
)

router = APIRouter()


def _device_payload(device: Device) -> dict:
    """Normaliza tipos PostgreSQL antes da validação/serialização Pydantic."""
    return {
        "id": device.id,
        "ip_address": str(device.ip_address),
        "mac_address": str(device.mac_address) if device.mac_address else None,
        "hostname": device.hostname,
        "fqdn": device.fqdn,
        "device_type": device.device_type.value if hasattr(device.device_type, "value") else str(device.device_type),
        "status": device.status.value if hasattr(device.status, "value") else str(device.status),
        "vendor": device.vendor,
        "model": device.model,
        "os_name": device.os_name,
        "os_version": device.os_version,
        "image_url": device.image_url,
        "snmp_enabled": device.snmp_enabled,
        "snmp_sys_name": device.snmp_sys_name,
        "snmp_sys_location": device.snmp_sys_location,
        "snmp_sys_uptime": device.snmp_sys_uptime,
        "network_segment": device.network_segment,
        "open_ports": device.open_ports,
        "is_visible": device.is_visible,
        "is_pinned": device.is_pinned,
        "tags": device.tags or [],
        "cpu_usage": device.cpu_usage,
        "memory_usage": device.memory_usage,
        "disk_usage": device.disk_usage,
        "first_seen": device.first_seen,
        "last_seen": device.last_seen,
        "created_at": device.created_at,
    }


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_type: str = Query(None),
    status: str = Query(None),
    snmp_enabled: bool = Query(None),
    is_visible: bool = Query(True),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista dispositivos com filtros e paginação."""
    query = select(Device)

    if is_visible is not None:
        query = query.where(Device.is_visible == is_visible)
    if device_type:
        query = query.where(Device.device_type == device_type)
    if status:
        query = query.where(Device.status == status)
    if snmp_enabled is not None:
        query = query.where(Device.snmp_enabled == snmp_enabled)
    if search:
        sf = f"%{search}%"
        query = query.where(
            or_(
                Device.ip_address.cast(str).ilike(sf),
                Device.hostname.ilike(sf),
                Device.vendor.ilike(sf),
                Device.model.ilike(sf),
                Device.snmp_sys_name.ilike(sf),
            )
        )

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    # SNMP counts
    snmp_active = (await db.execute(
        select(func.count()).where(Device.snmp_enabled == True, Device.is_visible == True)
    )).scalar()
    snmp_inactive = (await db.execute(
        select(func.count()).where(Device.snmp_enabled == False, Device.is_visible == True)
    )).scalar()

    query = (
        query.order_by(Device.last_seen.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    devices = result.scalars().all()

    return DeviceListResponse(
        items=[_device_payload(device) for device in devices],
        total=total,
        page=page,
        page_size=page_size,
        snmp_active_count=snmp_active,
        snmp_inactive_count=snmp_inactive,
    )


@router.get("/summary", response_model=DeviceSummary)
async def get_device_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna resumo geral dos dispositivos."""
    from datetime import timedelta

    total = (await db.execute(
        select(func.count()).where(Device.is_visible == True)
    )).scalar()
    online = (await db.execute(
        select(func.count()).where(
            Device.status == DeviceStatus.ONLINE, Device.is_visible == True
        )
    )).scalar()
    offline = (await db.execute(
        select(func.count()).where(
            Device.status == DeviceStatus.OFFLINE, Device.is_visible == True
        )
    )).scalar()
    snmp_on = (await db.execute(
        select(func.count()).where(
            Device.snmp_enabled == True, Device.is_visible == True
        )
    )).scalar()

    # By type
    type_query = await db.execute(
        select(Device.device_type, func.count())
        .where(Device.is_visible == True)
        .group_by(Device.device_type)
    )
    by_type = {row[0].value if hasattr(row[0], 'value') else row[0]: row[1] for row in type_query}

    # New last 24h
    yesterday = utcnow_naive() - timedelta(hours=24)
    new_24h = (await db.execute(
        select(func.count()).where(Device.first_seen >= yesterday)
    )).scalar()

    return DeviceSummary(
        total_devices=total,
        online=online,
        offline=offline,
        snmp_active=snmp_on,
        snmp_inactive=total - snmp_on,
        by_type=by_type,
        new_last_24h=new_24h,
    )


@router.get("/{device_id}/details")
async def get_device_details(
    device_id: UUID, hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    device = await db.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    cutoff = utcnow_naive() - timedelta(hours=hours)
    metrics = list((await db.execute(select(DeviceMetric).where(
        DeviceMetric.device_id == device_id, DeviceMetric.collected_at >= cutoff,
    ).order_by(DeviceMetric.collected_at).limit(3000))).scalars().all())
    interfaces = list((await db.execute(select(SNMPInterface).where(
        SNMPInterface.device_id == device_id
    ).order_by(SNMPInterface.if_index))).scalars().all())
    alerts = list((await db.execute(select(Alert).where(Alert.device_id == device_id).order_by(desc(Alert.triggered_at)).limit(50))).scalars().all())
    collections = list((await db.execute(select(SNMPCollection).where(
        SNMPCollection.device_id == device_id
    ).order_by(desc(SNMPCollection.collected_at)).limit(20))).scalars().all())
    log_filter = SyslogEvent.source_ip == str(device.ip_address)
    if device.hostname:
        log_filter = or_(log_filter, SyslogEvent.hostname == device.hostname)
    logs = list((await db.execute(select(SyslogEvent).where(log_filter).order_by(desc(SyslogEvent.received_at)).limit(200))).scalars().all())
    return {
        "device": {**_device_payload(device), "serial_number": device.serial_number,
                   "firmware_version": device.firmware_version, "snmp_version": device.snmp_version,
                   "snmp_sys_descr": device.snmp_sys_descr, "snmp_sys_contact": device.snmp_sys_contact,
                   "snmp_sys_object_id": device.snmp_sys_object_id},
        "metrics": [{"timestamp": x.collected_at.isoformat(), "cpu_usage": x.cpu_usage,
                     "memory_usage": x.memory_usage, "disk_usage": x.disk_usage,
                     "in_bps": x.in_bps, "out_bps": x.out_bps,
                     "utilization_in": x.utilization_in, "utilization_out": x.utilization_out,
                     "interfaces_up": x.interfaces_up, "interfaces_down": x.interfaces_down} for x in metrics],
        "interfaces": [{"id": str(x.id), "if_index": x.if_index,
                        "name": x.if_name or x.if_descr or f"if{x.if_index}", "alias": x.if_alias,
                        "admin_status": x.if_admin_status, "oper_status": x.if_oper_status,
                        "speed": x.if_high_speed or x.if_speed, "in_bps": x.in_bps, "out_bps": x.out_bps,
                        "utilization_in": x.utilization_in, "utilization_out": x.utilization_out,
                        "in_errors": x.if_in_errors, "out_errors": x.if_out_errors,
                        "in_discards": x.if_in_discards, "out_discards": x.if_out_discards} for x in interfaces],
        "snmp_collections": [{"id": str(x.id), "status": x.status, "duration_ms": x.duration_ms,
                              "collected_at": x.collected_at.isoformat(), "data": x.collection_data} for x in collections],
        "logs": [{"id": str(x.id), "timestamp": x.received_at.isoformat(), "severity": x.severity,
                  "app_name": x.app_name, "message": x.message} for x in logs],
        "alerts": [{"id": str(x.id), "title": x.title, "message": x.message, "severity": x.severity,
                    "status": x.status.value, "triggered_at": x.triggered_at.isoformat()} for x in alerts],
    }


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes de um dispositivo."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return _device_payload(device)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Atualiza dados de um dispositivo."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "device_type":
            setattr(device, field, DeviceType(value))
        else:
            setattr(device, field, value)

    await db.flush()
    await db.refresh(device)
    return _device_payload(device)


@router.delete("/{device_id}", status_code=204)
async def hide_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Oculta dispositivo (soft delete via is_visible=False)."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    device.is_visible = False
    await db.flush()


@router.post("/{device_id}/pin", response_model=DeviceResponse)
async def toggle_pin_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fixa/desfixa um dispositivo."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    device.is_pinned = not device.is_pinned
    await db.flush()
    await db.refresh(device)
    return _device_payload(device)
