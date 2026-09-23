# netguard/backend/app/tasks/snmp_tasks.py
"""
NetGuard - Celery tasks para coleta SNMP.
"""

from uuid import UUID

from loguru import logger
from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.tasks import celery_app
from app.database import async_session
from app.models.device import Device
from app.models.snmp import SNMPCollection, SNMPCommunity
from app.utils.async_runner import run_async


@celery_app.task(bind=True, name="netguard.run_snmp_collection", queue="snmp", soft_time_limit=180, time_limit=210)
def run_snmp_collection(self, device_id: str, community_string: str = "public", community_id: str = None):
    """Task: Coleta SNMP de um dispositivo."""
    logger.info("SNMP collection for device {}", device_id)

    from app.services.snmp_service import run_snmp_collection_for_device

    async def _record_failure(error: str, failure_status: str = "failed"):
        async with async_session() as db:
            db.add(SNMPCollection(
                device_id=UUID(device_id),
                community_id=UUID(community_id) if community_id else None,
                collection_data={}, status=failure_status, error_message=error[:2000],
            ))
            await db.commit()

    try:
        run_async(run_snmp_collection_for_device(
            device_id=UUID(device_id),
            community_string=community_string,
            community_id=UUID(community_id) if community_id else None,
        ))
        logger.info("SNMP collection complete for {}", device_id)
    except SoftTimeLimitExceeded:
        logger.error("SNMP collection timed out for {}", device_id)
        run_async(_record_failure("Celery soft time limit exceeded", "timeout"))
        return {"status": "timeout", "device_id": device_id}
    except Exception as e:
        logger.error("SNMP collection failed for {}: {}", device_id, e)
        run_async(_record_failure(str(e), "failed"))
        raise


@celery_app.task(bind=True, name="netguard.run_bulk_snmp_collection", queue="snmp")
def run_bulk_snmp_collection(self, community_id: str = None):
    """Task: Coleta SNMP em massa para todos os dispositivos com SNMP ativo."""
    logger.info("Bulk SNMP collection starting")

    async def _bulk():
        async with async_session() as db:
            query = select(Device).where(
                Device.snmp_enabled == True,
                Device.is_visible == True,
            )
            result = await db.execute(query)
            devices = result.scalars().all()

            community_string = "public"
            comm_uuid = None
            if community_id:
                comm_uuid = UUID(community_id)
                comm_result = await db.execute(
                    select(SNMPCommunity).where(SNMPCommunity.id == comm_uuid)
                )
                comm = comm_result.scalar_one_or_none()
                if comm:
                    community_string = comm.community_string
            else:
                # Use default community
                comm_result = await db.execute(
                    select(SNMPCommunity).where(SNMPCommunity.is_default == True)
                )
                comm = comm_result.scalar_one_or_none()
                if comm:
                    community_string = comm.community_string
                    comm_uuid = comm.id

            return [(str(d.id), community_string, str(comm_uuid) if comm_uuid else None) for d in devices]

    device_list = run_async(_bulk())
    logger.info("Bulk SNMP: {} devices to collect", len(device_list))

    queued = 0
    for dev_id, comm_str, comm_id in device_list:
        try:
            run_snmp_collection.apply_async(args=[dev_id, comm_str, comm_id], queue="snmp")
            queued += 1
        except Exception as e:
            logger.error("Could not queue SNMP for {}: {}", dev_id, e)

    logger.info("Bulk SNMP dispatched: {} of {}", queued, len(device_list))
    return {"queued": queued, "failed_to_queue": len(device_list) - queued, "total": len(device_list)}


@celery_app.task(name="netguard.snmp_auto_detect")
def snmp_auto_detect():
    """Task periódica: testa SNMP em dispositivos que ainda não foram verificados."""
    logger.info("SNMP auto-detect starting")

    from app.services.snmp_service import SNMPService

    async def _detect():
        service = SNMPService()
        async with async_session() as db:
            result = await db.execute(
                select(Device).where(
                    Device.snmp_enabled == False,
                    Device.is_visible == True,
                )
            )
            devices = result.scalars().all()

            # Get default community
            comm_result = await db.execute(
                select(SNMPCommunity).where(SNMPCommunity.is_default == True)
            )
            comm = comm_result.scalar_one_or_none()
            communities = [comm.community_string] if comm else ["public"]

            # Also try all active communities
            all_comms = await db.execute(
                select(SNMPCommunity).where(SNMPCommunity.is_active == True)
            )
            for c in all_comms.scalars().all():
                if c.community_string not in communities:
                    communities.append(c.community_string)

            detected = 0
            for device in devices:
                ip = str(device.ip_address)
                for community in communities:
                    is_active = await service.check_snmp(ip, community)
                    if is_active:
                        device.snmp_enabled = True
                        detected += 1
                        logger.info("SNMP detected on {} with community", ip)
                        break

            await db.commit()
            return detected

    count = run_async(_detect())
    logger.info("SNMP auto-detect: {} new devices detected", count)
    return {"detected": count}
