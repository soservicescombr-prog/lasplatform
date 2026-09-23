# netguard/agent/netguard_agent/agent.py
"""
NetGuard Agent — Scanner de vulnerabilidades local para hosts.
Instalável em Linux e Windows. Comunica com o servidor via HTTPS.
"""

import json
import glob
import os
import platform
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import psutil

# === Configuration ===
DEFAULT_CONFIG = {
    "server_url": "http://localhost:8000",
    "agent_token": "",
    "scan_interval_minutes": 60,
    "heartbeat_interval_seconds": 15,
    "metrics_interval_seconds": 15,
    "log_paths": [],
    "log_batch_size": 500,
    "state_path": str(Path.home() / ".netguard-agent-state.json"),
}


class NetGuardAgent:
    """Agente de scan de vulnerabilidades para host local."""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.server_url = self.config["server_url"].rstrip("/")
        self.token = self.config["agent_token"]
        self.hostname = socket.gethostname()
        self.platform = platform.system().lower()
        self.state = self._load_state()

    def _load_state(self) -> dict:
        try:
            with open(self.config["state_path"], encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError, TypeError):
            return {"log_offsets": {}}

    def _save_state(self):
        path = Path(self.config["state_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self.state, handle)
        temporary.replace(path)

    def _load_config(self, config_path: str = None) -> dict:
        """Carrega configuração do agente."""
        path = config_path or os.environ.get(
            "NETGUARD_AGENT_CONFIG",
            str(Path.home() / ".netguard-agent.json"),
        )
        config = DEFAULT_CONFIG.copy()
        if os.path.exists(path):
            with open(path) as f:
                config.update(json.load(f))
        return config

    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # === System Information ===

    def collect_metrics(self) -> dict:
        """Collects portable host utilization and cumulative I/O counters."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(Path.home().anchor or "/")
        network = psutil.net_io_counters()
        disk_io = psutil.disk_io_counters()
        try:
            load_1m, load_5m, load_15m = psutil.getloadavg()
        except (AttributeError, OSError):
            load_1m = load_5m = load_15m = None
        return {
            "cpu_usage": psutil.cpu_percent(interval=0.25), "memory_usage": memory.percent,
            "disk_usage": disk.percent, "load_1m": load_1m, "load_5m": load_5m, "load_15m": load_15m,
            "network_bytes_sent": network.bytes_sent, "network_bytes_recv": network.bytes_recv,
            "network_packets_sent": network.packets_sent, "network_packets_recv": network.packets_recv,
            "disk_read_bytes": getattr(disk_io, "read_bytes", 0) if disk_io else 0,
            "disk_write_bytes": getattr(disk_io, "write_bytes", 0) if disk_io else 0,
            "process_count": len(psutil.pids()),
            "boot_time": datetime.utcfromtimestamp(psutil.boot_time()).isoformat(),
            "details": {"cpu_count": psutil.cpu_count(), "memory_total": memory.total, "disk_total": disk.total},
        }

    def collect_log_entries(self) -> list[dict]:
        """Tails configured files without resending old content and survives rotation."""
        entries = []
        offsets = self.state.setdefault("log_offsets", {})
        limit = int(self.config.get("log_batch_size", 500))
        for configured in self.config.get("log_paths", []):
            candidates = [Path(item) for item in glob.glob(configured)] if any(c in configured for c in "*?[]") else [Path(configured)]
            for path in sorted(candidates):
                if not path.is_file() or len(entries) >= limit:
                    continue
                try:
                    size = path.stat().st_size
                    offset = int(offsets.get(str(path), 0))
                    if size < offset:  # rotation/truncation
                        offset = 0
                    with open(path, "r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        for line in handle:
                            if line.strip():
                                entries.append({"path": str(path), "message": line.rstrip()})
                            if len(entries) >= limit:
                                break
                        offsets[str(path)] = handle.tell()
                except (OSError, ValueError):
                    continue
        self._save_state()
        return entries

    def send_logs(self) -> int:
        previous_offsets = dict(self.state.get("log_offsets", {}))
        entries = self.collect_log_entries()
        if not entries:
            return 0
        try:
            response = requests.post(f"{self.server_url}/api/v1/agents/logs", json={"entries": entries},
                                     headers=self._api_headers(), timeout=30)
            if response.status_code == 200:
                return len(entries)
            print(f"[NetGuard Agent] Logs rejected: HTTP {response.status_code} - {response.text[:500]}")
        except requests.RequestException as exc:
            print(f"[NetGuard Agent] Error sending logs: {exc}")
        self.state["log_offsets"] = previous_offsets
        self._save_state()
        return 0

    def collect_os_info(self) -> dict:
        """Coleta informações do sistema operacional."""
        info = {
            "hostname": self.hostname,
            "platform": self.platform,
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "fqdn": socket.getfqdn(),
        }

        if self.platform == "linux":
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        key, _, value = line.strip().partition("=")
                        if key == "PRETTY_NAME":
                            info["os_pretty_name"] = value.strip('"')
            except FileNotFoundError:
                pass

        return info

    # === Open Ports ===

    def scan_open_ports(self) -> list[dict]:
        """Lista portas abertas no host."""
        ports = []

        if self.platform == "linux":
            try:
                result = subprocess.run(
                    ["ss", "-tlnp"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in result.stdout.split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 5:
                        addr = parts[3]
                        port = addr.split(":")[-1] if ":" in addr else None
                        process = parts[6] if len(parts) > 6 else ""
                        if port and port.isdigit():
                            ports.append({
                                "port": int(port),
                                "protocol": "tcp",
                                "address": addr,
                                "process": process,
                            })
            except Exception:
                pass

        elif self.platform == "windows":
            try:
                result = subprocess.run(
                    ["netstat", "-an", "-p", "TCP"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in result.stdout.split("\n"):
                    if "LISTENING" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            addr = parts[1]
                            port = addr.split(":")[-1]
                            if port.isdigit():
                                ports.append({
                                    "port": int(port),
                                    "protocol": "tcp",
                                    "address": addr,
                                })
            except Exception:
                pass

        return ports

    # === Installed Software / Runtimes ===

    def detect_runtimes(self) -> dict:
        """Detecta versões de runtimes instalados (Java, .NET, PHP, Python, Node.js)."""
        runtimes = {}

        checks = [
            ("java", ["java", "-version"], r"version\s+\"?([\d._]+)"),
            ("python3", ["python3", "--version"], r"Python\s+([\d.]+)"),
            ("node", ["node", "--version"], r"v([\d.]+)"),
            ("php", ["php", "--version"], r"PHP\s+([\d.]+)"),
            ("dotnet", ["dotnet", "--version"], r"([\d.]+)"),
            ("ruby", ["ruby", "--version"], r"ruby\s+([\d.]+)"),
            ("go", ["go", "version"], r"go([\d.]+)"),
            ("perl", ["perl", "-v"], r"v([\d.]+)"),
        ]

        for name, cmd, pattern in checks:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10,
                )
                output = result.stdout + result.stderr
                match = re.search(pattern, output)
                if match:
                    runtimes[name] = {
                        "version": match.group(1),
                        "path": self._find_executable(cmd[0]),
                    }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return runtimes

    def _find_executable(self, name: str) -> str:
        """Encontra o caminho do executável."""
        cmd = "which" if self.platform != "windows" else "where"
        try:
            result = subprocess.run(
                [cmd, name], capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip().split("\n")[0]
        except Exception:
            return ""

    # === Running Services ===

    def list_running_services(self) -> list[dict]:
        """Lista serviços em execução."""
        services = []

        if self.platform == "linux":
            try:
                result = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in result.stdout.split("\n"):
                    match = re.match(r"\s*(\S+\.service)\s+loaded\s+active\s+running\s+(.*)", line)
                    if match:
                        services.append({
                            "name": match.group(1),
                            "description": match.group(2).strip(),
                            "status": "running",
                        })
            except Exception:
                pass

        elif self.platform == "windows":
            try:
                result = subprocess.run(
                    ["wmic", "service", "where", "state='Running'", "get", "Name,DisplayName", "/format:csv"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        services.append({
                            "name": parts[2],
                            "description": parts[1],
                            "status": "running",
                        })
            except Exception:
                pass

        return services

    # === Pending Updates ===

    def check_pending_updates(self) -> list[dict]:
        """Verifica atualizações pendentes no SO."""
        updates = []

        if self.platform == "linux":
            # Debian/Ubuntu
            try:
                result = subprocess.run(
                    ["apt", "list", "--upgradable"],
                    capture_output=True, text=True, timeout=30,
                )
                for line in result.stdout.split("\n")[1:]:
                    if "/" in line:
                        pkg_name = line.split("/")[0]
                        updates.append({
                            "package": pkg_name,
                            "type": "apt",
                            "info": line.strip(),
                        })
            except FileNotFoundError:
                pass

            # RHEL/CentOS
            try:
                result = subprocess.run(
                    ["yum", "check-update", "-q"],
                    capture_output=True, text=True, timeout=30,
                )
                for line in result.stdout.split("\n"):
                    parts = line.split()
                    if len(parts) >= 3:
                        updates.append({
                            "package": parts[0],
                            "version": parts[1],
                            "type": "yum",
                        })
            except FileNotFoundError:
                pass

        return updates

    # === Vulnerability Analysis ===

    def analyze_vulnerabilities(self) -> list[dict]:
        """Analisa vulnerabilidades no host."""
        vulns = []

        # Check runtimes for known vulnerable versions
        runtimes = self.detect_runtimes()
        vuln_checks = {
            "java": [
                (r"^1\.[0-7]\.", "critical", "Java 7 ou anterior — End of Life, múltiplos CVEs"),
                (r"^1\.8\.0_([0-2]\d\d)", "high", "Java 8 versão antiga — atualizar para update mais recente"),
            ],
            "node": [
                (r"^(8|10|12|14|15|16)\.", "high", "Node.js versão sem suporte LTS ativo"),
            ],
            "python3": [
                (r"^3\.[0-7]\.", "medium", "Python 3.7 ou anterior sem suporte de segurança"),
            ],
            "php": [
                (r"^[5-7]\.", "high", "PHP 7.x ou anterior sem suporte de segurança"),
            ],
        }

        for runtime, checks in vuln_checks.items():
            if runtime in runtimes:
                version = runtimes[runtime]["version"]
                for pattern, severity, description in checks:
                    if re.match(pattern, version):
                        vulns.append({
                            "title": f"{runtime.capitalize()} versão vulnerável ({version})",
                            "severity": severity,
                            "description": description,
                            "remediation": f"Atualizar {runtime} para versão com suporte ativo",
                            "component": runtime,
                            "version": version,
                        })

        # Check for common misconfigurations
        if self.platform == "linux":
            # SSH config
            try:
                with open("/etc/ssh/sshd_config") as f:
                    ssh_config = f.read()

                if "PermitRootLogin yes" in ssh_config:
                    vulns.append({
                        "title": "SSH permite login como root",
                        "severity": "high",
                        "description": "PermitRootLogin está habilitado.",
                        "remediation": "Definir PermitRootLogin no em /etc/ssh/sshd_config",
                    })

                if "PasswordAuthentication yes" in ssh_config:
                    vulns.append({
                        "title": "SSH permite autenticação por senha",
                        "severity": "medium",
                        "description": "Autenticação por senha é vulnerável a brute force.",
                        "remediation": "Usar autenticação por chave SSH e definir PasswordAuthentication no",
                    })
            except (FileNotFoundError, PermissionError):
                pass

            # World-writable files
            try:
                result = subprocess.run(
                    ["find", "/etc", "-maxdepth", "1", "-perm", "-o+w", "-type", "f"],
                    capture_output=True, text=True, timeout=10,
                )
                writable_files = [f for f in result.stdout.strip().split("\n") if f]
                if writable_files:
                    vulns.append({
                        "title": "Arquivos de configuração com permissão world-writable",
                        "severity": "high",
                        "description": f"{len(writable_files)} arquivo(s) em /etc com escrita para todos.",
                        "remediation": "Remover permissão de escrita para 'other': chmod o-w <arquivo>",
                    })
            except Exception:
                pass

        return vulns

    # === Full Report ===

    def generate_report(self) -> dict:
        """Gera relatório completo do host."""
        report = {
            "report_type": "full_scan",
            "timestamp": datetime.utcnow().isoformat(),
            "os_info": self.collect_os_info(),
            "open_ports": self.scan_open_ports(),
            "runtime_versions": self.detect_runtimes(),
            "running_services": self.list_running_services(),
            "pending_updates": self.check_pending_updates(),
            "vulnerabilities": self.analyze_vulnerabilities(),
            "metrics": self.collect_metrics(),
        }

        # Counts
        vulns = report["vulnerabilities"]
        report["total_vulnerabilities"] = len(vulns)
        report["critical_count"] = sum(1 for v in vulns if v.get("severity") == "critical")
        report["high_count"] = sum(1 for v in vulns if v.get("severity") == "high")
        report["medium_count"] = sum(1 for v in vulns if v.get("severity") == "medium")
        report["low_count"] = sum(1 for v in vulns if v.get("severity") == "low")

        return report

    def send_report(self, report: dict) -> bool:
        """Envia relatório para o servidor NetGuard."""
        try:
            resp = requests.post(
                f"{self.server_url}/api/v1/agents/report",
                json=report,
                headers=self._api_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"[NetGuard Agent] API rejected report: HTTP {resp.status_code} - {resp.text[:500]}")
                return False
            return True
        except Exception as e:
            print(f"[NetGuard Agent] Error sending report: {e}")
            return False

    def heartbeat(self) -> bool:
        """Envia heartbeat para o servidor."""
        try:
            resp = requests.post(
                f"{self.server_url}/api/v1/agents/heartbeat",
                json={"hostname": self.hostname, "platform": self.platform,
                      "platform_version": platform.version(), "architecture": platform.machine(),
                      "python_version": platform.python_version(), "agent_version": "1.6.0",
                      "metrics": self.collect_metrics()},
                headers=self._api_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                remote = resp.json().get("config") or {}
                for key in ("log_paths", "heartbeat_interval_seconds", "metrics_interval_seconds", "log_batch_size"):
                    if key in remote:
                        self.config[key] = remote[key]
                return True
            print(f"[NetGuard Agent] Heartbeat rejected: HTTP {resp.status_code} - {resp.text[:500]}")
            return False
        except Exception:
            return False

    def run(self):
        """Loop principal do agente."""
        print(f"[NetGuard Agent] Starting on {self.hostname} ({self.platform})")
        print(f"[NetGuard Agent] Server: {self.server_url}")

        scan_interval = self.config["scan_interval_minutes"] * 60
        last_scan = 0
        last_heartbeat = 0

        while True:
            now = time.time()
            heartbeat_interval = max(10, int(self.config.get("heartbeat_interval_seconds", 15)))

            # Heartbeat
            if now - last_heartbeat >= heartbeat_interval:
                self.heartbeat()
                sent = self.send_logs()
                if sent:
                    print(f"[NetGuard Agent] {sent} log line(s) sent")
                last_heartbeat = now

            # Scan
            if now - last_scan >= scan_interval:
                print(f"[NetGuard Agent] Running scan...")
                report = self.generate_report()
                success = self.send_report(report)
                status = "sent" if success else "failed"
                print(f"[NetGuard Agent] Report {status} ({report['total_vulnerabilities']} vulns)")
                last_scan = now

            time.sleep(min(heartbeat_interval, 30))


if __name__ == "__main__":
    agent = NetGuardAgent()
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        report = agent.generate_report()
        print(json.dumps(report, indent=2, default=str))
    else:
        agent.run()
