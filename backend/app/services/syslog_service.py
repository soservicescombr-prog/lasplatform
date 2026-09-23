"""Syslog UDP/TCP receiver with PostgreSQL persistence."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select

from app.database import async_session
from app.models.alert import Alert
from app.models.device import Device
from app.models.log import SyslogEvent
from app.utils.postgres import as_inet
from app.utils.time import utcnow_naive

SYSLOG_SEVERITIES = {
    0: "emergency", 1: "alert", 2: "critical", 3: "error",
    4: "warning", 5: "notice", 6: "informational", 7: "debug",
}

SYSLOG_FACILITIES = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon", 4: "auth",
    5: "syslog", 6: "lpr", 7: "news", 8: "uucp", 9: "cron",
    10: "authpriv", 11: "ftp", 16: "local0", 17: "local1",
    18: "local2", 19: "local3", 20: "local4", 21: "local5",
    22: "local6", 23: "local7",
}

SECURITY_PATTERNS = [
    {"pattern": r"(?i)failed\s+password|authentication\s+failure|login\s+fail", "category": "auth_failure", "severity": "warning"},
    {"pattern": r"(?i)accepted\s+password|session\s+opened", "category": "auth_success", "severity": "notice"},
    {"pattern": r"(?i)invalid\s+user|unknown\s+user", "category": "invalid_user", "severity": "warning"},
    {"pattern": r"(?i)connection\s+refused|connection\s+reset", "category": "connection_issue", "severity": "notice"},
    {"pattern": r"(?i)segfault|segmentation\s+fault|core\s+dump", "category": "crash", "severity": "critical"},
    {"pattern": r"(?i)out\s+of\s+memory|oom\s+killer", "category": "resource_exhaustion", "severity": "critical"},
    {"pattern": r"(?i)disk\s+full|no\s+space\s+left", "category": "disk_full", "severity": "critical"},
    {"pattern": r"(?i)interface\s+down|link\s+down", "category": "interface_down", "severity": "warning"},
    {"pattern": r"(?i)firewall.*deny|iptables.*drop|blocked", "category": "firewall_block", "severity": "notice"},
    {"pattern": r"(?i)brute\s*force|repeated\s+login|too\s+many", "category": "brute_force", "severity": "critical"},
]


class SyslogMessage:
    """Normalized RFC 3164/5424 message."""

    def __init__(self, raw: str, source_ip: str, source_port: int | None, protocol: str):
        self.raw = raw.replace("\x00", "")
        self.source_ip = source_ip
        self.source_port = source_port
        self.protocol = protocol
        self.received_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.event_at = None
        self.facility = 1
        self.severity = 6
        self.hostname = source_ip
        self.app_name = None
        self.proc_id = None
        self.msg_id = None
        self.message = self.raw
        self.properties: dict[str, str | int | None] = {
            "transport": protocol,
            "source_port": source_port,
        }
        self.security_category = None
        self.security_severity = None
        self._parse()

    def _parse(self):
        pri_match = re.match(r"^<(\d{1,3})>(.*)$", self.raw, re.DOTALL)
        content = self.raw
        if pri_match:
            pri = min(int(pri_match.group(1)), 191)
            self.facility = pri >> 3
            self.severity = pri & 7
            content = pri_match.group(2)

        rfc5424 = re.match(
            r"^(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(-|\[.*?\])(?:\s+(.*))?$",
            content,
            re.DOTALL,
        )
        if rfc5424:
            version, stamp, host, app, procid, msgid, structured, message = rfc5424.groups()
            self.hostname = None if host == "-" else host
            self.app_name = None if app == "-" else app
            self.proc_id = None if procid == "-" else procid
            self.msg_id = None if msgid == "-" else msgid
            self.message = message or ""
            self.properties.update({"rfc": "5424", "version": version})
            if structured != "-":
                self.properties["structured_data"] = structured
                for key, value in re.findall(r'(\w+)="([^"]*)"', structured):
                    self.properties[key] = value
            try:
                self.event_at = datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                self.properties["reported_timestamp"] = stamp
            return

        rfc3164 = re.match(
            r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+([^:\[]+)(?:\[(\d+)\])?:\s?(.*)$",
            content,
            re.DOTALL,
        )
        if rfc3164:
            stamp, self.hostname, self.app_name, self.proc_id, self.message = rfc3164.groups()
            self.properties["rfc"] = "3164"
            try:
                parsed = datetime.strptime(stamp, "%b %d %H:%M:%S")
                self.event_at = parsed.replace(year=self.received_at.year)
            except ValueError:
                self.properties["reported_timestamp"] = stamp
            return

        fallback = re.match(r"^(\S+)\s+([^:]+):\s?(.*)$", content, re.DOTALL)
        if fallback:
            self.hostname, self.app_name, self.message = fallback.groups()

    @property
    def severity_name(self) -> str:
        return SYSLOG_SEVERITIES.get(self.severity, "informational")

    @property
    def facility_name(self) -> str:
        return SYSLOG_FACILITIES.get(self.facility, f"facility-{self.facility}")

    def match_security_pattern(self):
        for item in SECURITY_PATTERNS:
            if re.search(item["pattern"], self.message):
                self.security_category = item["category"]
                self.security_severity = item["severity"]
                return item
        return None

    def to_dict(self) -> dict:
        return {
            "received_at": self.received_at.isoformat(),
            "timestamp": self.received_at.isoformat(),
            "event_at": self.event_at.isoformat() if self.event_at else None,
            "source_ip": self.source_ip,
            "source_port": self.source_port,
            "protocol": self.protocol,
            "facility": self.facility_name,
            "severity": self.severity_name,
            "severity_num": self.severity,
            "hostname": self.hostname,
            "app_name": self.app_name,
            "proc_id": self.proc_id,
            "msg_id": self.msg_id,
            "message": self.message,
            "raw": self.raw,
            "properties": self.properties,
            "security_category": self.security_category,
            "security_severity": self.security_severity,
        }


syslog_buffer: list[dict] = []


class SyslogReceiver:
    """Concurrent UDP/TCP receiver. Database is authoritative; buffer is diagnostic."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5514, messages: Optional[list[dict]] = None):
        self.host = host
        self.port = port
        self.running = False
        self.messages = messages if messages is not None else []
        self.max_buffer = 1000
        self.udp_transport = None
        self.tcp_server = None
        self.udp_enabled = True
        self.tcp_enabled = True
        self.last_error: str | None = None
        self.received_count = 0
        self.persisted_count = 0
        self.failed_count = 0
        self.last_received_at: datetime | None = None
        self.last_persisted_at: datetime | None = None
        self.last_source: str | None = None

    async def start(self):
        self.running = True
        loop = asyncio.get_running_loop()
        started = []
        if self.udp_enabled:
            try:
                self.udp_transport, _ = await loop.create_datagram_endpoint(
                    lambda: SyslogProtocol(self), local_addr=(self.host, self.port), reuse_port=True
                )
                started.append("UDP")
            except Exception as exc:
                self.last_error = f"UDP: {exc}"
                logger.error("Syslog UDP listener failed on {}:{}: {}", self.host, self.port, exc)
        if self.tcp_enabled:
            try:
                self.tcp_server = await asyncio.start_server(
                    self._handle_tcp, self.host, self.port, reuse_port=True
                )
                started.append("TCP")
            except Exception as exc:
                self.last_error = f"TCP: {exc}"
                logger.error("Syslog TCP listener failed on {}:{}: {}", self.host, self.port, exc)
        if not started:
            self.running = False
            return
        logger.info("Syslog receiver listening on {}:{} ({})", self.host, self.port, "/".join(started))
        while self.running:
            await asyncio.sleep(1)

    async def _handle_tcp(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername") or ("unknown", 0)
        try:
            while self.running:
                data = await reader.readline()
                if not data:
                    break
                await self.process_message(data, peer, "tcp")
        except Exception as exc:
            logger.warning("Syslog TCP client {} failed: {}", peer, exc)
        finally:
            writer.close()
            await writer.wait_closed()

    def stop(self):
        self.running = False
        if self.udp_transport:
            self.udp_transport.close()
        if self.tcp_server:
            self.tcp_server.close()

    async def process_message(self, data: bytes, addr: tuple, protocol: str = "udp"):
        raw = data.decode("utf-8", errors="replace").strip()
        if not raw:
            return
        source_ip = str(addr[0])
        source_port = int(addr[1]) if len(addr) > 1 and isinstance(addr[1], int) else None
        msg = SyslogMessage(raw[:65535], source_ip, source_port, protocol)
        self.received_count += 1
        self.last_received_at = msg.received_at
        self.last_source = source_ip
        security_pattern = msg.match_security_pattern()
        msg_dict = msg.to_dict()
        self.messages.append(msg_dict)
        if len(self.messages) > self.max_buffer:
            del self.messages[:-self.max_buffer]

        try:
            async with async_session() as db:
                event = SyslogEvent(
                    received_at=msg.received_at,
                    event_at=msg.event_at,
                    source_ip=msg.source_ip,
                    source_port=msg.source_port,
                    protocol=msg.protocol,
                    facility=msg.facility_name,
                    severity=msg.severity_name,
                    severity_num=msg.severity,
                    hostname=msg.hostname,
                    app_name=msg.app_name,
                    proc_id=msg.proc_id,
                    msg_id=msg.msg_id,
                    message=msg.message,
                    raw=msg.raw,
                    properties=msg.properties,
                    security_category=msg.security_category,
                    security_severity=msg.security_severity,
                )
                db.add(event)
                if security_pattern and security_pattern["severity"] in ("critical", "alert"):
                    await self._create_security_alert(db, msg, security_pattern)
                await db.commit()
                self.persisted_count += 1
                self.last_persisted_at = utcnow_naive()
        except Exception as exc:
            self.failed_count += 1
            self.last_error = str(exc)
            logger.exception("Syslog persistence failed from {}: {}", source_ip, exc)

    async def _create_security_alert(self, db, msg: SyslogMessage, pattern: dict):
        result = await db.execute(select(Device).where(Device.ip_address == as_inet(msg.source_ip)))
        device = result.scalar_one_or_none()
        db.add(Alert(
            device_id=device.id if device else None,
            title=f"Syslog: {pattern['category'].replace('_', ' ').title()}",
            message=f"De {msg.source_ip}: {msg.message[:500]}",
            severity=pattern["severity"],
            category="syslog",
            details={
                "source_ip": msg.source_ip,
                "facility": msg.facility_name,
                "syslog_severity": msg.severity_name,
                "pattern": pattern["category"],
                "raw": msg.raw[:1000],
            },
        ))

    def health(self) -> dict:
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "udp": bool(self.udp_transport),
            "tcp": bool(self.tcp_server),
            "buffered_messages": len(self.messages),
            "last_error": self.last_error,
            "received_count": self.received_count,
            "persisted_count": self.persisted_count,
            "failed_count": self.failed_count,
            "last_received_at": self.last_received_at.isoformat() if self.last_received_at else None,
            "last_persisted_at": self.last_persisted_at.isoformat() if self.last_persisted_at else None,
            "last_source": self.last_source,
        }


class SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver: SyslogReceiver):
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr: tuple):
        asyncio.create_task(self.receiver.process_message(data, addr, "udp"))


syslog_receiver = SyslogReceiver(messages=syslog_buffer)
