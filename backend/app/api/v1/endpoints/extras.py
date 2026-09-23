# netguard/backend/app/api/v1/endpoints/extras.py
"""
NetGuard - Endpoints adicionais: Topology, Compliance, Threat Intel, Syslog, CMDB.
"""

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Any

from app.database import get_db
from app.core.deps import get_current_user, get_operator_user
from app.models.user import User
from app.models.device import Device
from app.models.inventory import InventoryItem, NetworkConnection
from app.services.inventory_service import backfill_device_inventory

router = APIRouter()


# ========================================
# S1 — TOPOLOGY
# ========================================

@router.get("/topology/data")
async def get_topology_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna dados para o mapa de topologia de rede."""
    # Nodes (devices)
    result = await db.execute(
        select(Device).where(Device.is_visible == True)
    )
    devices = result.scalars().all()

    nodes = [
        {
            "id": str(d.id),
            "label": d.hostname or str(d.ip_address),
            "ip": str(d.ip_address),
            "type": d.device_type.value if hasattr(d.device_type, 'value') else str(d.device_type),
            "status": d.status.value if hasattr(d.status, 'value') else str(d.status),
            "vendor": d.vendor,
            "snmp": d.snmp_enabled,
        }
        for d in devices
    ]

    # Edges (connections)
    conn_result = await db.execute(select(NetworkConnection))
    connections = conn_result.scalars().all()

    edges = [
        {
            "id": str(c.id),
            "source": str(c.source_device_id),
            "target": str(c.target_device_id),
            "source_if": c.source_interface,
            "target_if": c.target_interface,
            "type": c.connection_type,
            "status": c.status,
        }
        for c in connections
    ]

    # Auto-generate edges from same-subnet devices if no manual connections
    if not edges and len(nodes) > 1:
        subnet_groups: dict[str, list] = {}
        for d in devices:
            ip_str = str(d.ip_address)
            subnet = '.'.join(ip_str.split('.')[:3])
            subnet_groups.setdefault(subnet, []).append(str(d.id))

        for subnet, device_ids in subnet_groups.items():
            # Connect to first device in subnet (star topology approximation)
            if len(device_ids) > 1:
                hub = device_ids[0]
                for spoke in device_ids[1:]:
                    edges.append({
                        "id": f"auto-{hub}-{spoke}",
                        "source": hub,
                        "target": spoke,
                        "type": "inferred",
                        "status": "active",
                    })

    return {"nodes": nodes, "edges": edges}


class ConnectionCreate(BaseModel):
    source_device_id: UUID
    target_device_id: UUID
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    connection_type: str = "ethernet"


@router.post("/topology/connections")
async def create_connection(
    data: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    """Cria conexão manual entre dispositivos."""
    conn = NetworkConnection(**data.model_dump())
    db.add(conn)
    await db.flush()
    return {"message": "Conexão criada", "id": str(conn.id)}


# ========================================
# S3 — CMDB / INVENTORY
# ========================================

class InventoryCreate(BaseModel):
    device_id: UUID
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    department: Optional[str] = None
    responsible: Optional[str] = None
    location_building: Optional[str] = None
    location_floor: Optional[str] = None
    location_room: Optional[str] = None
    location_rack: Optional[str] = None
    criticality: str = "medium"
    environment: Optional[str] = None
    business_service: Optional[str] = None
    support_contract: Optional[str] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = None


class InventoryUpdate(BaseModel):
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    department: Optional[str] = None
    responsible: Optional[str] = None
    location_building: Optional[str] = None
    location_floor: Optional[str] = None
    location_room: Optional[str] = None
    location_rack: Optional[str] = None
    criticality: Optional[str] = None
    environment: Optional[str] = None
    business_service: Optional[str] = None
    support_contract: Optional[str] = None
    support_expiry: Optional[str] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = None


@router.get("/inventory")
async def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: str = Query(None),
    criticality: str = Query(None),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista itens de inventário/CMDB."""
    # Autocorreção: garante que dispositivos já descobertos apareçam mesmo que
    # tenham sido criados antes da sincronização automática da CMDB.
    await backfill_device_inventory(db)
    await db.flush()

    query = select(InventoryItem)
    if department:
        query = query.where(InventoryItem.department == department)
    if criticality:
        query = query.where(InventoryItem.criticality == criticality)
    if search:
        sf = f"%{search}%"
        query = query.where(
            InventoryItem.asset_tag.ilike(sf) |
            InventoryItem.responsible.ilike(sf) |
            InventoryItem.business_service.ilike(sf)
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    device_map = {}
    if items:
        device_result = await db.execute(
            select(Device).where(Device.id.in_([item.device_id for item in items]))
        )
        device_map = {device.id: device for device in device_result.scalars().all()}

    return {
        "items": [
            {
                "id": str(i.id), "device_id": str(i.device_id),
                "device_ip": str(device_map[i.device_id].ip_address) if i.device_id in device_map else None,
                "device_name": device_map[i.device_id].hostname if i.device_id in device_map else None,
                "device_vendor": device_map[i.device_id].vendor if i.device_id in device_map else None,
                "asset_tag": i.asset_tag, "serial_number": i.serial_number,
                "department": i.department, "responsible": i.responsible,
                "location_building": i.location_building, "location_room": i.location_room,
                "location_rack": i.location_rack, "criticality": i.criticality,
                "environment": i.environment, "business_service": i.business_service,
                "support_contract": i.support_contract,
                "custom_fields": i.custom_fields, "notes": i.notes,
            }
            for i in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/inventory", status_code=201)
async def create_inventory_item(
    data: InventoryCreate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    item = InventoryItem(**data.model_dump())
    db.add(item)
    await db.flush()
    return {"message": "Item criado", "id": str(item.id)}


@router.put("/inventory/{item_id}")
async def update_inventory_item(
    item_id: UUID, data: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(get_operator_user),
):
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    return {"message": "Item atualizado"}


# ========================================
# S4 — COMPLIANCE CHECKER
# ========================================

@router.get("/compliance/check")
async def run_compliance_check(
    device_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executa verificação de compliance (CIS/PCI-DSS)."""
    from app.services.compliance_service import ComplianceService
    service = ComplianceService(db)
    return await service.run_compliance_check(device_id)


# ========================================
# S5 — THREAT INTELLIGENCE
# ========================================

@router.get("/threat-intel/ip/{ip}")
async def check_ip_reputation(
    ip: str,
    current_user: User = Depends(get_current_user),
):
    """Verifica reputação de um IP em feeds de threat intelligence."""
    from app.services.threat_intel_service import ThreatIntelService
    service = ThreatIntelService()
    return await service.check_ip_reputation(ip)


@router.get("/threat-intel/cve/{cve_id}")
async def check_cve(
    cve_id: str,
    current_user: User = Depends(get_current_user),
):
    """Busca detalhes de um CVE (NVD + OTX)."""
    from app.services.threat_intel_service import ThreatIntelService
    service = ThreatIntelService()
    return await service.check_cve_details(cve_id)


@router.get("/threat-intel/latest")
async def get_latest_threats(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Busca últimas ameaças publicadas (AlienVault OTX)."""
    from app.services.threat_intel_service import ThreatIntelService
    service = ThreatIntelService()
    return await service.get_latest_threats(limit)


# ========================================
# S10 — SYSLOG
# ========================================

@router.get("/syslog/messages")
async def get_syslog_messages(
    limit: int = Query(100, ge=1, le=1000),
    severity: str = Query(None),
    source_ip: str = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Retorna últimas mensagens syslog recebidas."""
    from app.services.syslog_service import syslog_buffer

    messages = list(syslog_buffer)

    if severity:
        messages = [m for m in messages if m.get("severity") == severity]
    if source_ip:
        messages = [m for m in messages if m.get("source_ip") == source_ip]

    return {"messages": messages[-limit:], "total": len(messages)}


@router.get("/syslog/stats")
async def get_syslog_stats(
    current_user: User = Depends(get_current_user),
):
    """Estatísticas do syslog recebido."""
    from app.services.syslog_service import syslog_buffer

    messages = list(syslog_buffer)
    by_severity: dict[str, int] = {}
    by_source: dict[str, int] = {}
    security_events = 0

    for m in messages:
        sev = m.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        src = m.get("source_ip", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        if "security_category" in m:
            security_events += 1

    return {
        "total_messages": len(messages),
        "by_severity": by_severity,
        "by_source": dict(sorted(by_source.items(), key=lambda x: x[1], reverse=True)[:20]),
        "security_events": security_events,
    }
