// netguard/frontend/src/lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatBps(bps: number): string {
  if (bps === 0) return '0 bps'
  const k = 1000
  const sizes = ['bps', 'Kbps', 'Mbps', 'Gbps']
  const i = Math.floor(Math.log(bps) / Math.log(k))
  return `${parseFloat((bps / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function severityColor(severity: string): string {
  const map: Record<string, string> = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
    info: 'badge-info',
  }
  return map[severity] || 'badge-info'
}

export function deviceTypeLabel(type: string): string {
  const map: Record<string, string> = {
    switch: 'Switch',
    router: 'Router',
    firewall: 'Firewall',
    server: 'Servidor',
    desktop: 'Desktop',
    printer: 'Impressora',
    access_point: 'Access Point',
    ip_phone: 'Telefone IP',
    camera: 'Câmera',
    iot: 'IoT',
    unknown: 'Desconhecido',
  }
  return map[type] || type
}
