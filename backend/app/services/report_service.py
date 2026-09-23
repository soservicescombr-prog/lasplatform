# netguard/backend/app/services/report_service.py
"""
NetGuard - Service de geração de relatórios PDF e Excel.
Suporta: relatório executivo, vulnerabilidades, dispositivos, pentest.
"""

import io
from datetime import datetime
from typing import Optional
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DeviceStatus
from app.models.scan import VulnerabilityFinding, SeverityLevel, ScanJob
from app.models.alert import Alert, AlertStatus
from app.models.snmp import SNMPInterface


class ReportService:
    """Gerador de relatórios PDF e Excel."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # === PDF Reports ===

    async def generate_executive_pdf(self) -> io.BytesIO:
        """Gera relatório executivo em PDF com visão geral."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        elements = []

        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#1a5ff5'))
        h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceAfter=10)
        body_style = styles['BodyText']

        # Header
        elements.append(Paragraph("NetGuard — Relatório Executivo", title_style))
        elements.append(Paragraph(f"Gerado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}", body_style))
        elements.append(Spacer(1, 15*mm))

        # Device summary
        total_devices = (await self.db.execute(select(func.count()).where(Device.is_visible == True))).scalar() or 0
        online = (await self.db.execute(select(func.count()).where(Device.status == DeviceStatus.ONLINE, Device.is_visible == True))).scalar() or 0
        offline = total_devices - online
        snmp_on = (await self.db.execute(select(func.count()).where(Device.snmp_enabled == True, Device.is_visible == True))).scalar() or 0

        elements.append(Paragraph("1. Resumo de Dispositivos", h2_style))
        dev_data = [
            ['Métrica', 'Valor'],
            ['Total de dispositivos', str(total_devices)],
            ['Online', str(online)],
            ['Offline', str(offline)],
            ['Com SNMP ativo', str(snmp_on)],
        ]
        t = Table(dev_data, colWidths=[200, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5ff5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        # Vulnerability summary
        elements.append(Paragraph("2. Resumo de Vulnerabilidades", h2_style))
        vuln_counts = {}
        for level in SeverityLevel:
            c = (await self.db.execute(
                select(func.count()).where(VulnerabilityFinding.severity == level, VulnerabilityFinding.is_resolved == False)
            )).scalar() or 0
            vuln_counts[level.value] = c

        sev_colors = {'critical': '#dc2626', 'high': '#f97316', 'medium': '#eab308', 'low': '#3b82f6', 'info': '#6b7280'}
        vuln_data = [['Severidade', 'Quantidade']]
        for sev, count in vuln_counts.items():
            vuln_data.append([sev.upper(), str(count)])

        t2 = Table(vuln_data, colWidths=[200, 100])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5ff5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 10*mm))

        # Alerts summary
        elements.append(Paragraph("3. Alertas", h2_style))
        active_alerts = (await self.db.execute(select(func.count()).where(Alert.status == AlertStatus.ACTIVE))).scalar() or 0
        muted = (await self.db.execute(select(func.count()).where(Alert.is_muted == True))).scalar() or 0
        resolved = (await self.db.execute(select(func.count()).where(Alert.status == AlertStatus.RESOLVED))).scalar() or 0

        alert_data = [
            ['Status', 'Quantidade'],
            ['Ativos', str(active_alerts)],
            ['Mutados', str(muted)],
            ['Resolvidos', str(resolved)],
        ]
        t3 = Table(alert_data, colWidths=[200, 100])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5ff5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ]))
        elements.append(t3)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    async def generate_vulnerabilities_pdf(self, severity: str = None) -> io.BytesIO:
        """Gera relatório PDF detalhado de vulnerabilidades."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        elements = []

        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#1a5ff5'))
        elements.append(Paragraph("NetGuard — Relatório de Vulnerabilidades", title_style))
        elements.append(Paragraph(f"Gerado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}", styles['BodyText']))
        elements.append(Spacer(1, 8*mm))

        query = select(VulnerabilityFinding).where(VulnerabilityFinding.is_resolved == False)
        if severity:
            query = query.where(VulnerabilityFinding.severity == severity)
        query = query.order_by(VulnerabilityFinding.severity, VulnerabilityFinding.last_detected.desc())

        result = await self.db.execute(query)
        vulns = result.scalars().all()

        data = [['Severidade', 'Título', 'CVE', 'Porta', 'Serviço', 'CVSS', 'Remediação']]
        for v in vulns:
            data.append([
                v.severity.value.upper(),
                str(v.title)[:60],
                v.cve_id or '—',
                str(v.port) if v.port else '—',
                v.service_name or '—',
                str(v.cvss_score) if v.cvss_score else '—',
                str(v.remediation or '—')[:80],
            ])

        if len(data) > 1:
            t = Table(data, colWidths=[60, 160, 80, 40, 60, 40, 200], repeatRows=1)
            sev_row_colors = []
            for i, row in enumerate(data[1:], 1):
                if row[0] == 'CRITICAL':
                    sev_row_colors.append(('TEXTCOLOR', (0, i), (0, i), colors.HexColor('#dc2626')))
                elif row[0] == 'HIGH':
                    sev_row_colors.append(('TEXTCOLOR', (0, i), (0, i), colors.HexColor('#f97316')))

            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5ff5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ] + sev_row_colors))
            elements.append(t)
        else:
            elements.append(Paragraph("Nenhuma vulnerabilidade encontrada.", styles['BodyText']))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # === Excel Export ===

    async def generate_devices_excel(self) -> io.BytesIO:
        """Exporta lista de dispositivos em Excel."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dispositivos"

        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill(start_color="1A5FF5", end_color="1A5FF5", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )

        headers = ['IP', 'Hostname', 'MAC', 'Tipo', 'Status', 'Fabricante', 'Modelo', 'SO', 'SNMP', 'SNMP Name', 'Localização', 'Primeira vez', 'Última vez']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        result = await self.db.execute(
            select(Device).where(Device.is_visible == True).order_by(Device.ip_address)
        )
        devices = result.scalars().all()

        for row_idx, d in enumerate(devices, 2):
            values = [
                str(d.ip_address), d.hostname or '', d.mac_address or '',
                d.device_type.value if hasattr(d.device_type, 'value') else str(d.device_type),
                d.status.value if hasattr(d.status, 'value') else str(d.status),
                d.vendor or '', d.model or '',
                f"{d.os_name or ''} {d.os_version or ''}".strip(),
                'Sim' if d.snmp_enabled else 'Não',
                d.snmp_sys_name or '', d.snmp_sys_location or '',
                d.first_seen.strftime('%d/%m/%Y %H:%M') if d.first_seen else '',
                d.last_seen.strftime('%d/%m/%Y %H:%M') if d.last_seen else '',
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='left')

        # Auto-width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    async def generate_vulnerabilities_excel(self) -> io.BytesIO:
        """Exporta vulnerabilidades em Excel."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Vulnerabilidades"

        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill(start_color="DC2626", end_color="DC2626", fill_type="solid")

        headers = ['Severidade', 'CVSS', 'Título', 'CVE', 'Porta', 'Serviço', 'Versão', 'Remediação', 'Detectado em', 'Resolvido']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill

        result = await self.db.execute(
            select(VulnerabilityFinding).order_by(VulnerabilityFinding.severity, VulnerabilityFinding.last_detected.desc())
        )
        vulns = result.scalars().all()

        sev_fills = {
            'critical': PatternFill(start_color="FEE2E2", fill_type="solid"),
            'high': PatternFill(start_color="FFEDD5", fill_type="solid"),
            'medium': PatternFill(start_color="FEF9C3", fill_type="solid"),
        }

        for row_idx, v in enumerate(vulns, 2):
            sev = v.severity.value if hasattr(v.severity, 'value') else str(v.severity)
            values = [
                sev.upper(), v.cvss_score or '', v.title, v.cve_id or '',
                v.port or '', v.service_name or '', v.service_version or '',
                v.remediation or '', v.last_detected.strftime('%d/%m/%Y') if v.last_detected else '',
                'Sim' if v.is_resolved else 'Não',
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                if sev in sev_fills:
                    cell.fill = sev_fills[sev]

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
