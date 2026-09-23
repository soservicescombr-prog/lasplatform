# netguard/backend/app/services/discovery_service.py
"""
NetGuard - Service de Network Discovery.
Usa python-nmap para scan de rede, detecção de SO e serviços.
"""

import re
import subprocess
import tempfile
import threading
from typing import Optional
from uuid import UUID

import nmap
from loguru import logger
from sqlalchemy import select

from app.database import async_session
from app.config import get_settings
from app.models.device import Device, DeviceType, DeviceStatus
from app.models.inventory import InventoryItem
from app.utils.time import utcnow_naive
from app.utils.postgres import as_inet
from app.models.scan import ScanJob, ScanStatus

settings = get_settings()


class DiscoveryCancelled(Exception):
    """Sinaliza cancelamento solicitado pelo usuário durante o Nmap."""

# OUI prefix → vendor mapping (subset; expand as needed)
OUI_VENDORS = {
    "00:00:0C": "Cisco", "00:01:42": "Cisco", "00:1A:A1": "Cisco",
    "00:50:56": "VMware", "00:0C:29": "VMware", "00:05:69": "VMware",
    "00:1E:68": "Juniper", "00:1B:C5": "Juniper",
    "00:04:96": "Extreme Networks", "00:1A:8C": "Sophos",
    "00:23:04": "Dell", "00:14:22": "Dell", "F8:DB:88": "Dell",
    "00:25:B5": "HP", "3C:D9:2B": "HP", "00:1E:0B": "HP",
    "00:1A:4A": "Aruba", "00:0B:86": "Aruba",
    "00:17:F2": "Apple", "AC:DE:48": "Apple",
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi",
    "00:15:5D": "Microsoft Hyper-V",
    "08:00:27": "Oracle VirtualBox",
    "00:50:C2": "IEEE", "00:1C:7E": "Toshiba",
    "F0:9F:C2": "Ubiquiti", "24:A4:3C": "Ubiquiti",
    "00:1D:7E": "D-Link", "00:22:B0": "D-Link",
    "00:14:BF": "Linksys", "20:AA:4B": "Linksys",
    "00:1F:33": "Netgear", "A0:63:91": "Netgear",
    "4C:ED:FB": "MikroTik", "D4:CA:6D": "MikroTik",
    "00:E0:4C": "Realtek", "52:54:00": "QEMU/KVM",
}

# sysObjectID prefix → device type + model hints
DEVICE_TYPE_HINTS = {
    "router": ["router", "gateway", "cisco ios"],
    "switch": ["switch", "catalyst", "nexus", "aruba", "procurve"],
    "firewall": ["firewall", "fortigate", "asa", "pfsense", "sophos"],
    "server": ["server", "linux", "windows server", "vmware", "esxi", "ubuntu", "centos", "debian", "red hat"],
    "printer": ["printer", "laserjet", "xerox", "brother", "canon", "epson"],
    "access_point": ["access point", "ap ", "wireless", "unifi"],
    "desktop": ["windows 10", "windows 11", "workstation", "macos"],
    "ip_phone": ["phone", "voip", "sip"],
    "camera": ["camera", "hikvision", "dahua", "axis"],
}


def guess_vendor_from_mac(mac: str) -> Optional[str]:
    """Determina o fabricante pelo prefixo OUI do MAC address."""
    if not mac:
        return None
    prefix = mac.upper()[:8]
    return OUI_VENDORS.get(prefix)


def guess_device_type(os_info: str, vendor: str = None) -> DeviceType:
    """Heurística para classificar o tipo de dispositivo."""
    combined = f"{os_info or ''} {vendor or ''}".lower()
    for dtype, keywords in DEVICE_TYPE_HINTS.items():
        for kw in keywords:
            if kw in combined:
                return DeviceType(dtype)
    return DeviceType.UNKNOWN


class DiscoveryService:
    """Serviço principal de descoberta de rede."""

    def __init__(self):
        self.scanner = None

    def _ensure_scanner(self):
        if self.scanner is not None:
            return
        try:
            self.scanner = nmap.PortScanner(nmap_search_path=(settings.NMAP_PATH,))
        except nmap.PortScannerError as exc:
            raise RuntimeError(f"Nmap não encontrado em {settings.NMAP_PATH}") from exc

    def run_discovery(
        self,
        target: str,
        scan_job_id: str,
        options: dict = None,
        progress_callback=None,
    ) -> list[dict]:
        """
        Executa discovery scan com nmap.
        target: CIDR (192.168.1.0/24) ou range (192.168.1.1-50)
        """
        options = options or {}
        logger.info("Starting discovery scan on {}", target)

        if not re.fullmatch(r"[0-9a-fA-F.:/\-]+", target):
            raise ValueError("Alvo inválido. Informe IP, CIDR ou range numérico sem espaços")
        self._ensure_scanner()

        profile = options.get("profile", "quick")
        profiles = {
            "quick": [
                "-sn", "-PE", "-PS22,80,443,445,3389",
                "-PA21,22,80,443,3389", "-T4", "--max-retries", "2",
                "--host-timeout", "30s",
            ],
            "detailed": [
                "-sS", "-sV", "-O", "-T4", "--top-ports", "100",
                "--version-light", "--max-retries", "2", "--host-timeout", "120s",
            ],
            "no_ping": [
                "-Pn", "-sT", "-T4", "--top-ports", "20",
                "--max-retries", "1", "--host-timeout", "30s",
            ],
        }
        if profile not in profiles:
            raise ValueError(f"Perfil de discovery inválido: {profile}")

        command = [
            settings.NMAP_PATH,
            *profiles[profile],
            "--stats-every", "2s",
            "-oX", "-",
            target,
        ]
        stderr_lines: list[str] = []
        thread_errors: list[BaseException] = []
        process: subprocess.Popen | None = None

        def report(progress: int, stage: str, message: str):
            if progress_callback and progress_callback(progress, stage, message) is False:
                if process and process.poll() is None:
                    process.terminate()
                raise DiscoveryCancelled("Discovery cancelado pelo usuário")

        try:
            report(8, "preparing", f"Preparando Nmap ({profile})")
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file:
                process = subprocess.Popen(
                    command,
                    stdout=stdout_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    start_new_session=True,
                )

                def consume_stderr():
                    try:
                        assert process and process.stderr
                        for line in process.stderr:
                            line = line.strip()
                            if line:
                                stderr_lines.append(line)
                                del stderr_lines[:-40]
                            match = re.search(r"About\s+([\d.]+)%\s+done", line)
                            if match:
                                nmap_percent = min(100.0, float(match.group(1)))
                                mapped = min(90, 10 + int(nmap_percent * 0.8))
                                report(mapped, "scanning", f"Nmap: {nmap_percent:.1f}% do alvo examinado")
                    except BaseException as exc:
                        thread_errors.append(exc)
                        if process and process.poll() is None:
                            process.terminate()

                stderr_thread = threading.Thread(target=consume_stderr, daemon=True)
                stderr_thread.start()
                return_code = process.wait(timeout=settings.DEFAULT_SCAN_TIMEOUT)
                stderr_thread.join(timeout=5)
                stdout_file.seek(0)
                xml_output = stdout_file.read()

            if thread_errors:
                raise thread_errors[0]

            if return_code != 0:
                detail = "\n".join(stderr_lines[-8:]) or f"Nmap finalizou com código {return_code}"
                raise RuntimeError(detail)
            if not xml_output.strip():
                raise RuntimeError("Nmap não retornou resultado XML")

            self.scanner.analyse_nmap_xml_scan(
                nmap_xml_output=xml_output,
                nmap_err="\n".join(stderr_lines),
            )
        except subprocess.TimeoutExpired as exc:
            if process and process.poll() is None:
                process.kill()
            raise TimeoutError(
                f"Discovery excedeu o limite de {settings.DEFAULT_SCAN_TIMEOUT}s"
            ) from exc
        except DiscoveryCancelled:
            raise
        except FileNotFoundError as exc:
            raise RuntimeError(f"Nmap não encontrado em {settings.NMAP_PATH}") from exc
        except nmap.PortScannerError as exc:
            logger.error("Nmap scan error: {}", exc)
            raise RuntimeError(f"Falha ao interpretar resultado do Nmap: {exc}") from exc

        discovered = []
        hosts = self.scanner.all_hosts()
        total = len(hosts)
        logger.info("Found {} hosts", total)
        report(92, "processing", f"Processando {total} host(s) encontrado(s)")

        for idx, host in enumerate(hosts):
            host_data = self.scanner[host]
            device_info = self._extract_device_info(host, host_data)
            discovered.append(device_info)

            progress = 92 + int(((idx + 1) / max(total, 1)) * 5)
            report(progress, "processing", f"Processando host {idx + 1} de {total}")

        return discovered

    def run_port_scan(
        self,
        target: str,
        ports: str = "1-1024,3306,5432,6379,8080,8443,27017",
    ) -> dict:
        """Port scan detalhado em um host ou range."""
        logger.info("Port scan on {} ports {}", target, ports)
        self._ensure_scanner()

        self.scanner.scan(
            hosts=target,
            ports=ports,
            arguments="-sS -sV -T4 --version-intensity 5",
            timeout=300,
        )

        results = {}
        for host in self.scanner.all_hosts():
            host_ports = []
            for proto in self.scanner[host].all_protocols():
                for port in sorted(self.scanner[host][proto].keys()):
                    port_info = self.scanner[host][proto][port]
                    if port_info.get("state") == "open":
                        host_ports.append({
                            "port": port,
                            "protocol": proto,
                            "state": port_info.get("state"),
                            "service": port_info.get("name", ""),
                            "version": port_info.get("version", ""),
                            "product": port_info.get("product", ""),
                            "extra_info": port_info.get("extrainfo", ""),
                        })
            results[host] = host_ports
        return results

    def _extract_device_info(self, host: str, host_data: dict) -> dict:
        """Extrai informações do host a partir dos dados do nmap."""
        info = {
            "ip_address": host,
            "mac_address": None,
            "hostname": None,
            "vendor": None,
            "os_name": None,
            "os_version": None,
            "device_type": "unknown",
            "open_ports": [],
            "status": "online",
        }

        # Hostname
        if "hostnames" in host_data:
            for hname in host_data["hostnames"]:
                if hname.get("name"):
                    info["hostname"] = hname["name"]
                    break

        # MAC address and vendor
        if "addresses" in host_data:
            mac = host_data["addresses"].get("mac")
            if mac:
                info["mac_address"] = mac
                # Vendor from nmap
                if "vendor" in host_data and mac in host_data["vendor"]:
                    info["vendor"] = host_data["vendor"][mac]
                else:
                    info["vendor"] = guess_vendor_from_mac(mac)

        # OS detection
        if "osmatch" in host_data and host_data["osmatch"]:
            best_match = host_data["osmatch"][0]
            info["os_name"] = best_match.get("name", "")
            # Extract version from OS name
            version_match = re.search(r'(\d+[\.\d]*)', info["os_name"])
            if version_match:
                info["os_version"] = version_match.group(1)

        # Open ports
        for proto in host_data.get("tcp", {}):
            port_data = host_data["tcp"][proto]
            if port_data.get("state") == "open":
                info["open_ports"].append({
                    "port": proto,
                    "service": port_data.get("name", ""),
                    "version": port_data.get("version", ""),
                })

        # Device type classification
        info["device_type"] = guess_device_type(
            info.get("os_name", ""),
            info.get("vendor", ""),
        ).value

        return info

async def save_discovered_devices(
    discovered: list[dict],
    scan_job_id: UUID,
):
    """Persiste dispositivos descobertos no banco, tratando duplicatas."""
    async with async_session() as db:
        new_count = 0
        updated_count = 0
        inventory_created = 0

        for device_data in discovered:
            ip = device_data["ip_address"]

            # Check if device already exists
            result = await db.execute(
                select(Device).where(
                    Device.ip_address == as_inet(ip)
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                device = existing
                # Update existing device
                existing.status = DeviceStatus.ONLINE
                existing.last_seen = utcnow_naive()
                existing.hostname = device_data.get("hostname") or existing.hostname
                existing.mac_address = device_data.get("mac_address") or existing.mac_address
                existing.vendor = device_data.get("vendor") or existing.vendor
                existing.os_name = device_data.get("os_name") or existing.os_name
                existing.os_version = device_data.get("os_version") or existing.os_version
                if device_data.get("open_ports"):
                    existing.open_ports = device_data["open_ports"]
                if device_data.get("device_type") != "unknown":
                    existing.device_type = DeviceType(device_data["device_type"])
                updated_count += 1
            else:
                # Create new device
                device = Device(
                    ip_address=ip,
                    mac_address=device_data.get("mac_address"),
                    hostname=device_data.get("hostname"),
                    vendor=device_data.get("vendor"),
                    os_name=device_data.get("os_name"),
                    os_version=device_data.get("os_version"),
                    device_type=DeviceType(device_data.get("device_type", "unknown")),
                    status=DeviceStatus.ONLINE,
                    open_ports=device_data.get("open_ports", []),
                    snmp_enabled=False,
                )
                db.add(device)
                new_count += 1

            # Todo dispositivo descoberto deve possuir uma entrada básica na
            # CMDB. O flush garante o UUID dos dispositivos recém-criados.
            await db.flush()
            inventory_result = await db.execute(
                select(InventoryItem).where(InventoryItem.device_id == device.id)
            )
            if inventory_result.scalar_one_or_none() is None:
                db.add(InventoryItem(
                    device_id=device.id,
                    asset_tag=f"NG-{str(device.id).split('-')[0].upper()}",
                    criticality="medium",
                    custom_fields={
                        "source": "network_discovery",
                        "ip_address": ip,
                    },
                    notes="Item criado automaticamente pelo Network Discovery",
                ))
                inventory_created += 1

        # Update scan job
        result = await db.execute(
            select(ScanJob).where(ScanJob.id == scan_job_id)
        )
        scan_job = result.scalar_one_or_none()
        if scan_job:
            scan_job.devices_found = new_count + updated_count
            scan_job.status = ScanStatus.COMPLETED
            scan_job.completed_at = utcnow_naive()
            scan_job.progress = 100
            scan_job.results_summary = {
                "stage": "completed",
                "message": "Discovery concluído com sucesso",
                "new_devices": new_count,
                "updated_devices": updated_count,
                "inventory_created": inventory_created,
                "total_discovered": len(discovered),
            }

        await db.commit()
        logger.info(
            "Discovery complete: {} new, {} updated, {} inventory items created",
            new_count, updated_count, inventory_created,
        )

        return {
            "new": new_count,
            "updated": updated_count,
            "inventory_created": inventory_created,
        }
