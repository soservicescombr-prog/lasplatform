# netguard/backend/app/services/threat_intel_service.py
"""
NetGuard - Service de Threat Intelligence.
Integração com AlienVault OTX e feeds públicos de IoCs.
"""

from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger

from app.config import get_settings

settings = get_settings()

# AlienVault OTX API
OTX_API_URL = "https://otx.alienvault.com/api/v1"


class ThreatIntelService:
    """Serviço de inteligência de ameaças."""

    def __init__(self, otx_api_key: str = ""):
        self.otx_key = otx_api_key or getattr(settings, 'OTX_API_KEY', '')

    async def check_ip_reputation(self, ip: str) -> dict:
        """Verifica reputação de um IP em feeds de ameaças."""
        results = {
            "ip": ip,
            "is_malicious": False,
            "sources": [],
            "threat_score": 0,
            "details": [],
        }

        # AlienVault OTX
        if self.otx_key:
            otx_data = await self._check_otx_ip(ip)
            if otx_data:
                results["sources"].append("AlienVault OTX")
                results["details"].append(otx_data)
                if otx_data.get("pulse_count", 0) > 0:
                    results["is_malicious"] = True
                    results["threat_score"] = min(100, otx_data["pulse_count"] * 10)

        # AbuseIPDB (free tier)
        abuse_data = await self._check_abuseipdb(ip)
        if abuse_data:
            results["sources"].append("AbuseIPDB")
            results["details"].append(abuse_data)
            if abuse_data.get("abuse_confidence_score", 0) > 50:
                results["is_malicious"] = True
                results["threat_score"] = max(results["threat_score"], abuse_data["abuse_confidence_score"])

        return results

    async def check_cve_details(self, cve_id: str) -> dict:
        """Busca detalhes de um CVE na NVD + OTX."""
        result = {"cve_id": cve_id, "sources": []}

        # NVD
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{settings.NVD_API_URL}",
                    params={"cveId": cve_id},
                    headers={"apiKey": settings.NVD_API_KEY} if settings.NVD_API_KEY else {},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    vulns = data.get("vulnerabilities", [])
                    if vulns:
                        cve = vulns[0].get("cve", {})
                        descriptions = cve.get("descriptions", [])
                        desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")
                        metrics = cve.get("metrics", {})
                        cvss_v31 = metrics.get("cvssMetricV31", [])
                        score = cvss_v31[0].get("cvssData", {}).get("baseScore") if cvss_v31 else None
                        vector = cvss_v31[0].get("cvssData", {}).get("vectorString") if cvss_v31 else None

                        result["nvd"] = {
                            "description": desc,
                            "cvss_score": score,
                            "cvss_vector": vector,
                            "published": cve.get("published"),
                            "modified": cve.get("lastModified"),
                            "references": [r.get("url") for r in cve.get("references", [])[:5]],
                        }
                        result["sources"].append("NVD")
        except Exception as e:
            logger.debug("NVD lookup failed for {}: {}", cve_id, e)

        # OTX pulse search
        if self.otx_key:
            otx = await self._check_otx_cve(cve_id)
            if otx:
                result["otx"] = otx
                result["sources"].append("AlienVault OTX")

        return result

    async def get_latest_threats(self, limit: int = 20) -> list[dict]:
        """Busca últimas ameaças publicadas no OTX."""
        if not self.otx_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{OTX_API_URL}/pulses/subscribed",
                    params={"limit": limit, "page": 1},
                    headers={"X-OTX-API-KEY": self.otx_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        {
                            "id": p.get("id"),
                            "name": p.get("name"),
                            "description": (p.get("description") or "")[:300],
                            "created": p.get("created"),
                            "tags": p.get("tags", [])[:10],
                            "adversary": p.get("adversary"),
                            "targeted_countries": p.get("targeted_countries", []),
                            "indicators_count": len(p.get("indicators", [])),
                        }
                        for p in data.get("results", [])
                    ]
        except Exception as e:
            logger.error("OTX latest threats failed: {}", e)
        return []

    async def _check_otx_ip(self, ip: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{OTX_API_URL}/indicators/IPv4/{ip}/general",
                    headers={"X-OTX-API-KEY": self.otx_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "pulse_count": data.get("pulse_info", {}).get("count", 0),
                        "country": data.get("country_name"),
                        "asn": data.get("asn"),
                        "reputation": data.get("reputation", 0),
                        "pulses": [
                            {"name": p.get("name"), "created": p.get("created")}
                            for p in data.get("pulse_info", {}).get("pulses", [])[:5]
                        ],
                    }
        except Exception:
            pass
        return None

    async def _check_otx_cve(self, cve_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{OTX_API_URL}/indicators/cve/{cve_id}/general",
                    headers={"X-OTX-API-KEY": self.otx_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "pulse_count": data.get("pulse_info", {}).get("count", 0),
                        "pulses": [
                            {"name": p.get("name"), "tags": p.get("tags", [])}
                            for p in data.get("pulse_info", {}).get("pulses", [])[:5]
                        ],
                    }
        except Exception:
            pass
        return None

    async def _check_abuseipdb(self, ip: str) -> Optional[dict]:
        """Check básico via AbuseIPDB (sem API key = limitado)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                abuseipdb_key = getattr(settings, 'ABUSEIPDB_API_KEY', '')
                if not abuseipdb_key:
                    return None
                resp = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": ip, "maxAgeInDays": 90},
                    headers={"Key": abuseipdb_key, "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    d = resp.json().get("data", {})
                    return {
                        "abuse_confidence_score": d.get("abuseConfidenceScore", 0),
                        "total_reports": d.get("totalReports", 0),
                        "country": d.get("countryCode"),
                        "isp": d.get("isp"),
                        "usage_type": d.get("usageType"),
                        "is_public": d.get("isPublic"),
                    }
        except Exception:
            pass
        return None
