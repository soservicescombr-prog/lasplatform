# netguard/backend/app/api/v1/router.py
"""
NetGuard - API v1 Router. Agrega todos os endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, devices, scans, alerts, dashboard, snmp, agents, reports, extras, logs

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(users.router, prefix="/users", tags=["Usuários"])
api_router.include_router(devices.router, prefix="/devices", tags=["Dispositivos"])
api_router.include_router(scans.router, prefix="/scans", tags=["Scans"])
api_router.include_router(snmp.router, prefix="/snmp", tags=["SNMP"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alertas"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agentes"])
api_router.include_router(reports.router, prefix="/reports", tags=["Relatórios"])
api_router.include_router(extras.router, prefix="/extras", tags=["Topology, CMDB, Compliance, Threat Intel, Syslog"])
api_router.include_router(logs.router, prefix="/logs", tags=["Logs e Métricas"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
