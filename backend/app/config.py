# netguard/backend/app/config.py
"""
NetGuard - Configurações centralizadas da aplicação.
Carrega variáveis de ambiente via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Configurações globais do NetGuard."""

    # === App ===
    APP_NAME: str = "NetGuard"
    APP_VERSION: str = "1.5.0"
    APP_DESCRIPTION: str = "Network Security & Monitoring Platform"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # === Server ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # === Database ===
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "netguard"
    DB_USER: str = "netguard"
    DB_PASSWORD: str = "NetGuard2026"
    DATABASE_URL: Optional[str] = None

    # === Redis ===
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # === JWT Auth ===
    SECRET_KEY: str = "03c051732abd545da7404e8a43c1fa34d794bba242efde7a3ec92e86ba606a8d"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # === SMTP (Alerts/Notifications) ===
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "netguard@localhost"
    SMTP_TLS: bool = True

    # === Scan Defaults ===
    DEFAULT_SCAN_TIMEOUT: int = 600
    MAX_CONCURRENT_SCANS: int = 5
    NMAP_PATH: str = "/usr/bin/nmap"
    SCHEDULE_TIMEZONE: str = "America/Sao_Paulo"

    # === NVD/CVE API ===
    NVD_API_KEY: str = ""
    NVD_API_URL: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    OTX_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""

    # === Syslog ===
    SYSLOG_ENABLED: bool = True
    SYSLOG_HOST: str = "0.0.0.0"
    SYSLOG_PORT: int = 514
    SYSLOG_EXTERNAL_PORT: int = 514
    SYSLOG_UDP_ENABLED: bool = True
    SYSLOG_TCP_ENABLED: bool = True
    SYSLOG_RETENTION_DAYS: int = 30

    # === Agent ===
    AGENT_TOKEN_EXPIRE_DAYS: int = 365
    AGENT_HEARTBEAT_INTERVAL: int = 60
    AGENT_OFFLINE_SECONDS: int = 180
    DEVICE_OFFLINE_FAILURES: int = 3
    METRICS_RETENTION_DAYS: int = 30
    AVAILABILITY_CONCURRENCY: int = 50

    @property
    def database_url_computed(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
