# netguard/backend/app/services/snmp_service.py
"""
NetGuard - Service de Coleta SNMP.
Usa pysnmplib para consultar dispositivos via SNMP v1/v2c/v3.
"""

import asyncio
from typing import Optional
from uuid import UUID

from loguru import logger
from pysnmp.hlapi.v1arch.asyncio import *
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.device import Device
from app.utils.time import utcnow_naive
from app.models.snmp import SNMPCommunity, SNMPCollection, SNMPInterface
from app.models.metric import DeviceMetric
from app.config import get_settings

settings = get_settings()

# Standard OIDs
OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysObjectID": "1.3.6.1.2.1.1.2.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
}

# Interface table OIDs (ifTable / ifXTable)
IF_OIDS = {
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifType": "1.3.6.1.2.1.2.2.1.3",
    "ifMtu": "1.3.6.1.2.1.2.2.1.4",
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
    "ifPhysAddress": "1.3.6.1.2.1.2.2.1.6",
    "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
    "ifInErrors": "1.3.6.1.2.1.2.2.1.14",
    "ifInDiscards": "1.3.6.1.2.1.2.2.1.13",
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",
    "ifOutErrors": "1.3.6.1.2.1.2.2.1.20",
    "ifOutDiscards": "1.3.6.1.2.1.2.2.1.19",
    "ifInUcastPkts": "1.3.6.1.2.1.2.2.1.11",
    "ifOutUcastPkts": "1.3.6.1.2.1.2.2.1.17",
}

# ifXTable (64-bit counters)
IFX_OIDS = {
    "ifName": "1.3.6.1.2.1.31.1.1.1.1",
    "ifHighSpeed": "1.3.6.1.2.1.31.1.1.1.15",
    "ifAlias": "1.3.6.1.2.1.31.1.1.1.18",
    "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
    "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10",
    "ifInBroadcastPkts": "1.3.6.1.2.1.31.1.1.1.3",
    "ifOutBroadcastPkts": "1.3.6.1.2.1.31.1.1.1.5",
}

# Host Resources MIB (for servers/desktops)
HR_OIDS = {
    "hrProcessorLoad": "1.3.6.1.2.1.25.3.3.1.2",
    "hrStorageDescr": "1.3.6.1.2.1.25.2.3.1.3",
    "hrStorageSize": "1.3.6.1.2.1.25.2.3.1.5",
    "hrStorageUsed": "1.3.6.1.2.1.25.2.3.1.6",
    "hrStorageAllocationUnits": "1.3.6.1.2.1.25.2.3.1.4",
    "hrMemorySize": "1.3.6.1.2.1.25.2.2.0",
}

IF_TYPE_NAMES = {
    1: "other", 6: "ethernetCsmacd", 24: "softwareLoopback",
    53: "propVirtual", 62: "fastEther", 117: "gigabitEthernet",
    131: "tunnel", 135: "l2vlan", 136: "l3ipvlan",
    161: "ieee8023adLag", 209: "bridge", 230: "atm",
}


class SNMPService:
    """Serviço de coleta SNMP."""

    async def check_snmp(
        self,
        ip: str,
        community: str = "public",
        port: int = 161,
        timeout: float = 3.0,
    ) -> bool:
        """Testa se SNMP está ativo no dispositivo."""
        try:
            snmpDispatcher = SnmpDispatcher()
            errorIndication, errorStatus, _, varBinds = await get_cmd(
                snmpDispatcher,
                CommunityData(community),
                await UdpTransportTarget.create((ip, port), timeout=timeout, retries=settings.SNMP_REQUEST_RETRIES),
                ObjectType(ObjectIdentity(OIDS["sysDescr"])),
            )
            snmpDispatcher.transport_dispatcher.close_dispatcher()
            return errorIndication is None and errorStatus == 0
        except Exception:
            return False
        finally:
            try:
                snmpDispatcher.transport_dispatcher.close_dispatcher()
            except Exception:
                pass

    async def collect_system_info(
        self,
        ip: str,
        community: str = "public",
        port: int = 161,
    ) -> dict:
        """Coleta informações do sistema via SNMP."""
        result = {}
        try:
            snmpDispatcher = SnmpDispatcher()
            oid_list = [ObjectType(ObjectIdentity(oid)) for oid in OIDS.values()]

            errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                snmpDispatcher,
                CommunityData(community),
                await UdpTransportTarget.create((ip, port), timeout=settings.SNMP_REQUEST_TIMEOUT_SECONDS, retries=settings.SNMP_REQUEST_RETRIES),
                *oid_list,
            )
            snmpDispatcher.transport_dispatcher.close_dispatcher()

            if errorIndication or errorStatus:
                logger.warning("SNMP error on {}: {} {}", ip, errorIndication, errorStatus)
                return result

            oid_keys = list(OIDS.keys())
            for i, varBind in enumerate(varBinds):
                if i < len(oid_keys):
                    result[oid_keys[i]] = str(varBind[1])

        except Exception as e:
            logger.error("SNMP collection error on {}: {}", ip, e)
        finally:
            try:
                snmpDispatcher.transport_dispatcher.close_dispatcher()
            except Exception:
                pass

        return result

    async def collect_interfaces(
        self,
        ip: str,
        community: str = "public",
        port: int = 161,
    ) -> list[dict]:
        """Coleta dados de todas as interfaces (ifTable + ifXTable)."""
        interfaces = {}

        try:
            snmpDispatcher = SnmpDispatcher()
            transport = await UdpTransportTarget.create((ip, port), timeout=settings.SNMP_REQUEST_TIMEOUT_SECONDS, retries=settings.SNMP_REQUEST_RETRIES)
            auth = CommunityData(community)

            # Walk ifTable
            for oid_name, oid_str in IF_OIDS.items():
                async for errorIndication, errorStatus, errorIndex, varBinds in walk_cmd(
                    snmpDispatcher, auth, transport,
                    ObjectType(ObjectIdentity(oid_str)),
                ):
                    if errorIndication or errorStatus:
                        break
                    for varBind in varBinds:
                        oid = str(varBind[0])
                        value = varBind[1]
                        # Extract ifIndex from OID
                        if_index = int(oid.split(".")[-1])
                        if if_index not in interfaces:
                            interfaces[if_index] = {"if_index": if_index}

                        if oid_name == "ifPhysAddress":
                            # Format MAC
                            mac_hex = value.prettyPrint()
                            interfaces[if_index][oid_name] = mac_hex
                        else:
                            interfaces[if_index][oid_name] = (
                                int(value) if isinstance(value, (int,)) or str(value).isdigit()
                                else str(value)
                            )

            # Walk ifXTable
            for oid_name, oid_str in IFX_OIDS.items():
                async for errorIndication, errorStatus, errorIndex, varBinds in walk_cmd(
                    snmpDispatcher, auth, transport,
                    ObjectType(ObjectIdentity(oid_str)),
                ):
                    if errorIndication or errorStatus:
                        break
                    for varBind in varBinds:
                        oid = str(varBind[0])
                        value = varBind[1]
                        if_index = int(oid.split(".")[-1])
                        if if_index in interfaces:
                            interfaces[if_index][oid_name] = (
                                int(value) if str(value).isdigit() else str(value)
                            )

            snmpDispatcher.transport_dispatcher.close_dispatcher()

        except Exception as e:
            logger.error("SNMP interface collection error on {}: {}", ip, e)
        finally:
            try:
                snmpDispatcher.transport_dispatcher.close_dispatcher()
            except Exception:
                pass

        # Convert to list and add type names
        result = []
        for if_idx, data in interfaces.items():
            if_type = data.get("ifType")
            if if_type:
                data["ifTypeName"] = IF_TYPE_NAMES.get(int(if_type), f"type-{if_type}")
            result.append(data)

        return sorted(result, key=lambda x: x.get("if_index", 0))

    async def _numeric_walk(self, ip: str, community: str, oid: str) -> dict[int, float]:
        values = {}
        dispatcher = SnmpDispatcher()
        try:
            target = await UdpTransportTarget.create(
                (ip, 161), timeout=settings.SNMP_REQUEST_TIMEOUT_SECONDS,
                retries=settings.SNMP_REQUEST_RETRIES,
            )
            async for error_indication, error_status, _, var_binds in walk_cmd(
                dispatcher, CommunityData(community), target, ObjectType(ObjectIdentity(oid)),
            ):
                if error_indication or error_status:
                    break
                for var_bind in var_binds:
                    try:
                        values[int(str(var_bind[0]).split(".")[-1])] = float(var_bind[1])
                    except (TypeError, ValueError):
                        continue
        finally:
            dispatcher.transport_dispatcher.close_dispatcher()
        return values

    async def collect_performance(self, ip: str, community: str) -> dict:
        """Generic HOST-RESOURCES plus common Cisco CPU/memory tables."""
        result = {}
        cpu = await self._numeric_walk(ip, community, HR_OIDS["hrProcessorLoad"])
        if not cpu:  # CISCO-PROCESS-MIB cpmCPUTotal5minRev
            cpu = await self._numeric_walk(ip, community, "1.3.6.1.4.1.9.9.109.1.1.1.1.8")
        if cpu:
            result["cpu_usage"] = sum(cpu.values()) / len(cpu)

        descr = {}
        # Text walk only for identifying RAM/disk storage rows.
        dispatcher = SnmpDispatcher()
        try:
            target = await UdpTransportTarget.create((ip, 161), timeout=settings.SNMP_REQUEST_TIMEOUT_SECONDS,
                                                     retries=settings.SNMP_REQUEST_RETRIES)
            async for error_indication, error_status, _, var_binds in walk_cmd(
                dispatcher, CommunityData(community), target,
                ObjectType(ObjectIdentity(HR_OIDS["hrStorageDescr"])),
            ):
                if error_indication or error_status:
                    break
                for var_bind in var_binds:
                    descr[int(str(var_bind[0]).split(".")[-1])] = str(var_bind[1])
        finally:
            dispatcher.transport_dispatcher.close_dispatcher()
        size = await self._numeric_walk(ip, community, HR_OIDS["hrStorageSize"])
        used = await self._numeric_walk(ip, community, HR_OIDS["hrStorageUsed"])
        rows = {idx: (used[idx] / size[idx] * 100) for idx in size if size[idx] > 0 and idx in used}
        memory_rows = [pct for idx, pct in rows.items() if "memory" in descr.get(idx, "").lower() or "ram" in descr.get(idx, "").lower()]
        disk_rows = [pct for idx, pct in rows.items() if any(token in descr.get(idx, "").lower() for token in ("/", "disk", "fixed"))]
        if memory_rows:
            result["memory_usage"] = max(memory_rows)
        else:
            # CISCO-MEMORY-POOL-MIB (used/free by memory pool).
            cisco_used = await self._numeric_walk(ip, community, "1.3.6.1.4.1.9.9.48.1.1.1.5")
            cisco_free = await self._numeric_walk(ip, community, "1.3.6.1.4.1.9.9.48.1.1.1.6")
            pools = [cisco_used[idx] / (cisco_used[idx] + cisco_free[idx]) * 100
                     for idx in cisco_used if idx in cisco_free and cisco_used[idx] + cisco_free[idx] > 0]
            if pools:
                result["memory_usage"] = max(pools)
        if disk_rows:
            result["disk_usage"] = max(disk_rows)
        result["storage"] = [{"index": idx, "description": descr.get(idx), "usage": pct} for idx, pct in rows.items()]
        return result


async def run_snmp_collection_for_device(
    device_id: UUID,
    community_string: str = "public",
    community_id: UUID = None,
):
    """Executa coleta SNMP completa para um dispositivo e salva no banco."""
    service = SNMPService()

    async with async_session() as db:
        result = await db.execute(select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            logger.error("Device {} not found", device_id)
            return

        ip = str(device.ip_address)
        logger.info("SNMP collection for {} ({})", ip, device.hostname or "")

        start_time = utcnow_naive()

        # Each device is bounded independently; a slow MIB walk cannot block the fleet.
        async with asyncio.timeout(settings.SNMP_DEVICE_TIMEOUT_SECONDS):
            sys_info = await service.collect_system_info(ip, community_string)
            if_data = await service.collect_interfaces(ip, community_string) if sys_info else []
            performance = await service.collect_performance(ip, community_string) if sys_info else {}

        if sys_info:
            device.snmp_enabled = True
            device.snmp_sys_descr = sys_info.get("sysDescr")
            device.snmp_sys_name = sys_info.get("sysName")
            device.snmp_sys_location = sys_info.get("sysLocation")
            device.snmp_sys_contact = sys_info.get("sysContact")
            device.snmp_sys_uptime = sys_info.get("sysUpTime")
            device.snmp_sys_object_id = sys_info.get("sysObjectID")
            if community_id:
                device.snmp_community_id = community_id
            device.cpu_usage = performance.get("cpu_usage")
            device.memory_usage = performance.get("memory_usage")
            device.disk_usage = performance.get("disk_usage")
        else:
            device.snmp_enabled = False

        for iface in if_data:
            existing = await db.execute(
                select(SNMPInterface).where(
                    SNMPInterface.device_id == device_id,
                    SNMPInterface.if_index == iface["if_index"],
                )
            )
            existing_if = existing.scalar_one_or_none()

            if existing_if:
                # Calculate rates from deltas
                current_in = iface.get("ifHCInOctets") or iface.get("ifInOctets", 0) or 0
                current_out = iface.get("ifHCOutOctets") or iface.get("ifOutOctets", 0) or 0
                time_delta = (
                    utcnow_naive() - (existing_if.last_collected or start_time)
                ).total_seconds()
                if time_delta > 0:
                    in_delta = current_in - (existing_if.if_in_octets or 0)
                    out_delta = current_out - (existing_if.if_out_octets or 0)
                    existing_if.in_bps = max(0, (in_delta * 8) / time_delta)
                    existing_if.out_bps = max(0, (out_delta * 8) / time_delta)

                    speed = iface.get("ifHighSpeed") or iface.get("ifSpeed") or 0
                    speed_bps = int(speed) * 1_000_000 if iface.get("ifHighSpeed") else int(speed)
                    if speed_bps > 0:
                        existing_if.utilization_in = min(100, (existing_if.in_bps / speed_bps) * 100)
                        existing_if.utilization_out = min(100, (existing_if.out_bps / speed_bps) * 100)

                # Update counters
                existing_if.if_name = iface.get("ifName") or existing_if.if_name
                existing_if.if_descr = iface.get("ifDescr") or existing_if.if_descr
                existing_if.if_alias = iface.get("ifAlias") or existing_if.if_alias
                existing_if.if_admin_status = iface.get("ifAdminStatus")
                existing_if.if_oper_status = iface.get("ifOperStatus")
                existing_if.if_in_octets = current_in
                existing_if.if_out_octets = current_out
                existing_if.if_in_errors = iface.get("ifInErrors", 0) or 0
                existing_if.if_out_errors = iface.get("ifOutErrors", 0) or 0
                existing_if.if_in_discards = iface.get("ifInDiscards", 0) or 0
                existing_if.if_out_discards = iface.get("ifOutDiscards", 0) or 0
                existing_if.last_collected = utcnow_naive()
                history = list(existing_if.metrics_history or [])
                history.append({"timestamp": existing_if.last_collected.isoformat(), "in_bps": existing_if.in_bps,
                                "out_bps": existing_if.out_bps, "utilization_in": existing_if.utilization_in,
                                "utilization_out": existing_if.utilization_out, "in_errors": existing_if.if_in_errors,
                                "out_errors": existing_if.if_out_errors})
                existing_if.metrics_history = history[-2880:]
            else:
                # Create new interface record
                new_if = SNMPInterface(
                    device_id=device_id,
                    if_index=iface["if_index"],
                    if_name=iface.get("ifName"),
                    if_descr=iface.get("ifDescr"),
                    if_alias=iface.get("ifAlias"),
                    if_type=iface.get("ifType"),
                    if_type_name=iface.get("ifTypeName"),
                    if_mtu=iface.get("ifMtu"),
                    if_speed=iface.get("ifSpeed"),
                    if_high_speed=iface.get("ifHighSpeed"),
                    if_phys_address=iface.get("ifPhysAddress"),
                    if_admin_status=iface.get("ifAdminStatus"),
                    if_oper_status=iface.get("ifOperStatus"),
                    if_in_octets=iface.get("ifHCInOctets") or iface.get("ifInOctets", 0) or 0,
                    if_out_octets=iface.get("ifHCOutOctets") or iface.get("ifOutOctets", 0) or 0,
                    if_in_errors=iface.get("ifInErrors", 0) or 0,
                    if_out_errors=iface.get("ifOutErrors", 0) or 0,
                    if_in_discards=iface.get("ifInDiscards", 0) or 0,
                    if_out_discards=iface.get("ifOutDiscards", 0) or 0,
                )
                db.add(new_if)

        # 3. Save collection log
        duration = int((utcnow_naive() - start_time).total_seconds() * 1000)
        collection_log = SNMPCollection(
            device_id=device_id,
            community_id=community_id,
            collection_data={"system": sys_info, "performance": performance, "interfaces_count": len(if_data)},
            status="completed" if sys_info else "failed",
            duration_ms=duration,
        )
        db.add(collection_log)

        interface_rows = list((await db.execute(select(SNMPInterface).where(
            SNMPInterface.device_id == device_id
        ))).scalars().all())
        db.add(DeviceMetric(
            device_id=device_id, cpu_usage=device.cpu_usage, memory_usage=device.memory_usage,
            disk_usage=device.disk_usage, in_bps=sum(float(x.in_bps or 0) for x in interface_rows),
            out_bps=sum(float(x.out_bps or 0) for x in interface_rows),
            utilization_in=max([float(x.utilization_in or 0) for x in interface_rows] or [0]),
            utilization_out=max([float(x.utilization_out or 0) for x in interface_rows] or [0]),
            interfaces_up=sum(1 for x in interface_rows if x.if_oper_status == 1),
            interfaces_down=sum(1 for x in interface_rows if x.if_oper_status != 1),
            details={"sys_object_id": device.snmp_sys_object_id},
        ))

        await db.commit()
        logger.info(
            "SNMP collection for {} complete: {} interfaces in {}ms",
            ip, len(if_data), duration,
        )
