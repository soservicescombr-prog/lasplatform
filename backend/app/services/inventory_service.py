"""Sincronização básica entre dispositivos descobertos e a CMDB."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.inventory import InventoryItem


async def backfill_device_inventory(db: AsyncSession) -> int:
    """Cria itens básicos para dispositivos antigos ainda ausentes na CMDB."""
    result = await db.execute(
        select(Device)
        .outerjoin(InventoryItem, InventoryItem.device_id == Device.id)
        .where(InventoryItem.id.is_(None))
    )
    devices = result.scalars().all()
    if not devices:
        return 0

    statement = insert(InventoryItem).values([
        {
            "device_id": device.id,
            "asset_tag": f"NG-{str(device.id).split('-')[0].upper()}",
            "criticality": "medium",
            "custom_fields": {
                "source": "network_discovery",
                "ip_address": str(device.ip_address),
            },
            "notes": "Item criado automaticamente pelo Network Discovery",
        }
        for device in devices
    ]).on_conflict_do_nothing(index_elements=[InventoryItem.device_id])
    insert_result = await db.execute(statement)
    return max(insert_result.rowcount or 0, 0)
