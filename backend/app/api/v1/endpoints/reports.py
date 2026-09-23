# netguard/backend/app/api/v1/endpoints/reports.py
"""
NetGuard - Endpoints de exportação de relatórios (PDF e Excel).
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.report_service import ReportService

router = APIRouter()


@router.get("/executive/pdf")
async def export_executive_pdf(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta relatório executivo em PDF."""
    service = ReportService(db)
    buffer = await service.generate_executive_pdf()
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=netguard_executive_report.pdf"},
    )


@router.get("/vulnerabilities/pdf")
async def export_vulnerabilities_pdf(
    severity: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta relatório de vulnerabilidades em PDF."""
    service = ReportService(db)
    buffer = await service.generate_vulnerabilities_pdf(severity)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=netguard_vulnerabilities.pdf"},
    )


@router.get("/devices/excel")
async def export_devices_excel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta lista de dispositivos em Excel."""
    service = ReportService(db)
    buffer = await service.generate_devices_excel()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=netguard_devices.xlsx"},
    )


@router.get("/vulnerabilities/excel")
async def export_vulnerabilities_excel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta vulnerabilidades em Excel."""
    service = ReportService(db)
    buffer = await service.generate_vulnerabilities_excel()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=netguard_vulnerabilities.xlsx"},
    )
