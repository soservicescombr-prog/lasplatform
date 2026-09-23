"""Testes do executor Nmap e do progresso do Network Discovery."""

from pathlib import Path

import pytest

from app.services import discovery_service
from app.services.discovery_service import DiscoveryCancelled, DiscoveryService


FAKE_NMAP = r'''#!/usr/bin/env python3
import sys
import time

if "-V" in sys.argv:
    print("Nmap version 7.94 ( https://nmap.org )")
    raise SystemExit(0)

print("Stats: 0:00:01 elapsed; About 25.00% done", file=sys.stderr, flush=True)
time.sleep(0.05)
print("Stats: 0:00:02 elapsed; About 75.00% done", file=sys.stderr, flush=True)
print("""<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sn 192.168.0.0/24" start="1" startstr="test" version="7.94" xmloutputversion="1.05">
  <scaninfo type="ping" protocol="ip" numservices="0" services=""/>
  <verbose level="0"/><debugging level="0"/>
  <host><status state="up" reason="echo-reply" reason_ttl="64"/>
    <address addr="192.168.0.10" addrtype="ipv4"/>
    <hostnames><hostname name="test-host" type="PTR"/></hostnames>
  </host>
  <runstats><finished time="2" timestr="test" elapsed="1.0" summary="done" exit="success"/>
    <hosts up="1" down="0" total="1"/>
  </runstats>
</nmaprun>""")
'''


def _fake_nmap(tmp_path: Path) -> Path:
    executable = tmp_path / "nmap"
    executable.write_text(FAKE_NMAP, encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_discovery_reports_progress_and_returns_hosts(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery_service.settings, "NMAP_PATH", str(_fake_nmap(tmp_path)))
    updates = []

    result = DiscoveryService().run_discovery(
        "192.168.0.0/24",
        "00000000-0000-0000-0000-000000000001",
        {"profile": "quick"},
        lambda progress, stage, message: updates.append((progress, stage, message)) or True,
    )

    assert len(result) == 1
    assert result[0]["ip_address"] == "192.168.0.10"
    assert result[0]["hostname"] == "test-host"
    assert any(stage == "scanning" and progress >= 30 for progress, stage, _ in updates)
    assert updates[-1][1] == "processing"


def test_discovery_stops_when_progress_callback_cancels(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery_service.settings, "NMAP_PATH", str(_fake_nmap(tmp_path)))

    with pytest.raises(DiscoveryCancelled):
        DiscoveryService().run_discovery(
            "192.168.0.0/24",
            "00000000-0000-0000-0000-000000000001",
            {"profile": "quick"},
            lambda progress, stage, message: stage != "scanning",
        )


@pytest.mark.parametrize("target", ["192.168.0.0/24; rm -rf /", "example.com", "192.168.0.0/24 --script vuln"])
def test_discovery_rejects_unsafe_targets(target):
    with pytest.raises(ValueError):
        DiscoveryService().run_discovery(target, "scan", {"profile": "quick"})
