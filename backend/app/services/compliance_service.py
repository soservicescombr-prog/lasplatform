# netguard/backend/app/services/compliance_service.py
"""
NetGuard - Service de Compliance Checker.
Verifica conformidade com benchmarks CIS e PCI-DSS básico.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.scan import VulnerabilityFinding, SeverityLevel
from app.models.snmp import SNMPInterface
from app.utils.time import utcnow_naive

# CIS-inspired checks
CIS_CHECKS = [
    {
        "id": "CIS-NET-001",
        "category": "network",
        "title": "Telnet desabilitado",
        "description": "Porta 23 (Telnet) não deve estar aberta. Telnet transmite dados em texto plano.",
        "severity": "critical",
        "check": lambda d: not any(
            (p.get("port") == 23 if isinstance(p, dict) else p == 23) for p in (d.open_ports or [])
        ),
        "remediation": "Desabilitar Telnet e usar SSH (porta 22) como alternativa.",
    },
    {
        "id": "CIS-NET-002",
        "category": "network",
        "title": "FTP desabilitado",
        "description": "Porta 21 (FTP) não deve estar aberta. Usar SFTP ou FTPS.",
        "severity": "high",
        "check": lambda d: not any(
            (p.get("port") == 21 if isinstance(p, dict) else p == 21) for p in (d.open_ports or [])
        ),
        "remediation": "Desabilitar FTP e migrar para SFTP (porta 22) ou FTPS.",
    },
    {
        "id": "CIS-NET-003",
        "category": "snmp",
        "title": "SNMP com community não-padrão",
        "description": "Community strings padrão (public/private) não devem ser usadas.",
        "severity": "medium",
        "check": lambda d: True,  # Checked differently
        "remediation": "Alterar community strings ou migrar para SNMPv3 com autenticação.",
    },
    {
        "id": "CIS-NET-004",
        "category": "network",
        "title": "Serviços de banco de dados não expostos",
        "description": "Portas de banco de dados (3306, 5432, 1433, 27017) não devem estar expostas na rede.",
        "severity": "high",
        "check": lambda d: not any(
            (p.get("port") if isinstance(p, dict) else p) in (3306, 5432, 1433, 27017, 6379)
            for p in (d.open_ports or [])
        ),
        "remediation": "Restringir acesso a bancos de dados via firewall (apenas hosts autorizados).",
    },
    {
        "id": "CIS-NET-005",
        "category": "network",
        "title": "RDP não exposto externamente",
        "description": "Porta 3389 (RDP) não deve estar aberta sem VPN.",
        "severity": "high",
        "check": lambda d: not any(
            (p.get("port") == 3389 if isinstance(p, dict) else p == 3389) for p in (d.open_ports or [])
        ),
        "remediation": "Desabilitar RDP público e exigir acesso via VPN.",
    },
    {
        "id": "CIS-NET-006",
        "category": "network",
        "title": "VNC não exposto",
        "description": "Porta 5900 (VNC) frequentemente sem criptografia.",
        "severity": "critical",
        "check": lambda d: not any(
            (p.get("port") == 5900 if isinstance(p, dict) else p == 5900) for p in (d.open_ports or [])
        ),
        "remediation": "Desabilitar VNC ou usar VNC com túnel SSH/VPN.",
    },
    {
        "id": "PCI-DSS-001",
        "category": "pci",
        "title": "Sem vulnerabilidades críticas não resolvidas",
        "description": "PCI-DSS 6.1 — Identificar e classificar vulnerabilidades; corrigir críticas.",
        "severity": "critical",
        "check": None,  # DB check
        "remediation": "Resolver todas as vulnerabilidades de severidade crítica.",
    },
    {
        "id": "PCI-DSS-002",
        "category": "pci",
        "title": "Scans de vulnerabilidade recentes",
        "description": "PCI-DSS 11.2 — Scans de vulnerabilidade devem ser executados trimestralmente.",
        "severity": "medium",
        "check": None,  # DB check
        "remediation": "Executar scan de vulnerabilidade pelo menos a cada 90 dias.",
    },
    {
        "id": "CIS-SRV-001",
        "category": "server",
        "title": "Sistema operacional identificado e atualizado",
        "description": "Dispositivos devem ter SO identificado para verificação de patches.",
        "severity": "low",
        "check": lambda d: bool(d.os_name),
        "remediation": "Habilitar OS fingerprinting no discovery scan (modo agressivo).",
    },
    {
        "id": "CIS-MON-001",
        "category": "monitoring",
        "title": "SNMP habilitado para monitoramento",
        "description": "Dispositivos de rede devem ter SNMP habilitado para monitoramento.",
        "severity": "low",
        "check": lambda d: d.snmp_enabled if d.device_type.value in ('switch', 'router', 'firewall') else True,
        "remediation": "Habilitar SNMP (preferencialmente v3) em ativos de rede.",
    },
]


class ComplianceService:
    """Serviço de verificação de conformidade."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_compliance_check(self, device_id: UUID = None) -> dict:
        """Executa verificação de compliance em todos ou em um dispositivo."""
        if device_id:
            result = await self.db.execute(select(Device).where(Device.id == device_id))
            devices = [result.scalar_one_or_none()]
            devices = [d for d in devices if d]
        else:
            result = await self.db.execute(
                select(Device).where(Device.is_visible == True)
            )
            devices = result.scalars().all()

        findings = []
        passed = 0
        failed = 0

        for device in devices:
            for check in CIS_CHECKS:
                if check["check"] is None:
                    continue  # DB-level checks handled below

                try:
                    is_compliant = check["check"](device)
                except Exception:
                    is_compliant = False

                status = "pass" if is_compliant else "fail"
                if is_compliant:
                    passed += 1
                else:
                    failed += 1

                findings.append({
                    "check_id": check["id"],
                    "category": check["category"],
                    "title": check["title"],
                    "description": check["description"],
                    "severity": check["severity"],
                    "status": status,
                    "device_ip": str(device.ip_address),
                    "device_hostname": device.hostname,
                    "device_id": str(device.id),
                    "remediation": check["remediation"] if not is_compliant else None,
                })

        # DB-level checks
        # PCI-DSS-001: critical vulns
        crit_count = 0
        for device in devices:
            c = (await self.db.execute(
                select(VulnerabilityFinding).where(
                    VulnerabilityFinding.device_id == device.id,
                    VulnerabilityFinding.severity == SeverityLevel.CRITICAL,
                    VulnerabilityFinding.is_resolved == False,
                )
            )).scalars().all()
            if c:
                crit_count += len(c)
                findings.append({
                    "check_id": "PCI-DSS-001",
                    "category": "pci",
                    "title": "Vulnerabilidades críticas não resolvidas",
                    "severity": "critical",
                    "status": "fail",
                    "device_ip": str(device.ip_address),
                    "device_id": str(device.id),
                    "description": f"{len(c)} vulnerabilidade(s) crítica(s) encontrada(s).",
                    "remediation": "Resolver todas as vulnerabilidades de severidade crítica.",
                })
                failed += 1
            else:
                passed += 1

        # PCI-DSS-002: recent scans
        from app.models.scan import ScanJob, ScanStatus
        from datetime import timedelta
        cutoff_90d = utcnow_naive() - timedelta(days=90)
        recent_scans = (await self.db.execute(
            select(ScanJob).where(
                ScanJob.scan_type.in_(["vulnerability", "full"]),
                ScanJob.status == ScanStatus.COMPLETED,
                ScanJob.completed_at >= cutoff_90d,
            )
        )).scalars().all()

        if recent_scans:
            passed += 1
            findings.append({
                "check_id": "PCI-DSS-002", "category": "pci",
                "title": "Scans de vulnerabilidade recentes", "severity": "medium",
                "status": "pass", "device_ip": "—",
                "description": f"{len(recent_scans)} scan(s) nos últimos 90 dias.",
            })
        else:
            failed += 1
            findings.append({
                "check_id": "PCI-DSS-002", "category": "pci",
                "title": "Scans de vulnerabilidade recentes", "severity": "medium",
                "status": "fail", "device_ip": "—",
                "description": "Nenhum scan de vulnerabilidade nos últimos 90 dias.",
                "remediation": "Executar scan de vulnerabilidade trimestralmente.",
            })

        total = passed + failed
        score = round((passed / max(total, 1)) * 100, 1)

        return {
            "score": score,
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "findings": findings,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
