// netguard/frontend/src/pages/DashboardPage.tsx
import { useEffect, useState } from 'react'
import { dashboardApi } from '@/services/api'
import type { DashboardOverview } from '@/types'
import {
  Network, Wifi, Shield, Bug, Bell,
  AlertTriangle, Radar, TrendingUp, Server,
  Monitor, Printer, Router,
} from 'lucide-react'
import { cn } from '@/lib/utils'

function StatCard({
  label,
  value,
  icon: Icon,
  color = 'brand',
  sub,
}: {
  label: string
  value: number | string
  icon: React.ElementType
  color?: string
  sub?: string
}) {
  const colorMap: Record<string, string> = {
    brand: 'bg-brand-50 text-brand-600 dark:bg-brand-950 dark:text-brand-400',
    green: 'bg-green-50 text-green-600 dark:bg-green-950 dark:text-green-400',
    red: 'bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400',
    orange: 'bg-orange-50 text-orange-600 dark:bg-orange-950 dark:text-orange-400',
    yellow: 'bg-yellow-50 text-yellow-600 dark:bg-yellow-950 dark:text-yellow-400',
  }

  return (
    <div className="card-padded flex items-start gap-4">
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center shrink-0', colorMap[color])}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-surface-900 dark:text-white">{value}</p>
        <p className="text-sm text-surface-500">{label}</p>
        {sub && <p className="text-xs text-surface-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function SeverityBar({ label, count, total, color }: {
  label: string; count: number; total: number; color: string
}) {
  const pct = total > 0 ? (count / total) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-medium text-surface-500 w-16 text-right">{label}</span>
      <div className="flex-1 h-2 bg-surface-100 dark:bg-surface-800 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-surface-600 dark:text-surface-400 w-8 text-right">{count}</span>
    </div>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = () => dashboardApi.overview()
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Radar className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  if (!data) return null

  const vulnTotal =
    (data.vulnerabilities.by_severity.critical || 0) +
    (data.vulnerabilities.by_severity.high || 0) +
    (data.vulnerabilities.by_severity.medium || 0) +
    (data.vulnerabilities.by_severity.low || 0) +
    (data.vulnerabilities.by_severity.info || 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-surface-900 dark:text-white">Dashboard</h1>
        <p className="text-sm text-surface-500 mt-0.5">Visão geral da rede e segurança</p>
      </div>

      {/* Top stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Dispositivos"
          value={data.devices.total}
          icon={Network}
          color="brand"
          sub={`${data.devices.online} online · ${data.devices.offline} offline`}
        />
        <StatCard
          label="SNMP ativos"
          value={data.devices.snmp_active}
          icon={Wifi}
          color="green"
          sub={`${data.devices.snmp_inactive} sem SNMP`}
        />
        <StatCard
          label="Vulnerabilidades"
          value={data.vulnerabilities.total_open}
          icon={Bug}
          color={data.vulnerabilities.by_severity.critical > 0 ? 'red' : 'orange'}
          sub={`${data.vulnerabilities.by_severity.critical || 0} críticas`}
        />
        <StatCard
          label="Alertas ativos"
          value={data.alerts.active}
          icon={Bell}
          color={data.alerts.critical > 0 ? 'red' : 'yellow'}
          sub={`${data.alerts.critical} críticos · ${data.alerts.muted} mutados`}
        />
      </div>

      {/* Second row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Vulnerabilities by severity */}
        <div className="card-padded">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Vulnerabilidades por severidade
          </h2>
          <div className="space-y-3">
            <SeverityBar label="Critical" count={data.vulnerabilities.by_severity.critical || 0} total={vulnTotal} color="bg-red-500" />
            <SeverityBar label="High" count={data.vulnerabilities.by_severity.high || 0} total={vulnTotal} color="bg-orange-500" />
            <SeverityBar label="Medium" count={data.vulnerabilities.by_severity.medium || 0} total={vulnTotal} color="bg-yellow-500" />
            <SeverityBar label="Low" count={data.vulnerabilities.by_severity.low || 0} total={vulnTotal} color="bg-blue-500" />
            <SeverityBar label="Info" count={data.vulnerabilities.by_severity.info || 0} total={vulnTotal} color="bg-gray-400" />
          </div>
        </div>

        {/* Devices by type */}
        <div className="card-padded">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4 flex items-center gap-2">
            <Server className="w-4 h-4" />
            Dispositivos por tipo
          </h2>
          <div className="space-y-2">
            {Object.entries(data.devices.by_type).map(([type, count]) => {
              const iconMap: Record<string, React.ElementType> = {
                switch: Router, router: Router, server: Server,
                desktop: Monitor, printer: Printer,
              }
              const Icon = iconMap[type] || Network
              return (
                <div key={type} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-surface-400" />
                    <span className="text-sm text-surface-600 dark:text-surface-400 capitalize">{type}</span>
                  </div>
                  <span className="text-sm font-mono font-medium text-surface-900 dark:text-white">{count}</span>
                </div>
              )
            })}
            {Object.keys(data.devices.by_type).length === 0 && (
              <p className="text-sm text-surface-400 text-center py-4">Nenhum dispositivo encontrado</p>
            )}
          </div>
        </div>

        {/* Quick actions & agents */}
        <div className="space-y-4">
          <div className="card-padded">
            <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Atividade
            </h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Scans ativos</span>
                <span className="font-mono font-medium text-surface-900 dark:text-white">{data.scans.active}</span>
              </div>
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Scans (últimos 7 dias)</span>
                <span className="font-mono font-medium text-surface-900 dark:text-white">{data.scans.last_week}</span>
              </div>
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Novos dispositivos (24h)</span>
                <span className="font-mono font-medium text-surface-900 dark:text-white">{data.devices.new_last_24h}</span>
              </div>
            </div>
          </div>

          <div className="card-padded">
            <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Agentes
            </h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Total instalados</span>
                <span className="font-mono font-medium text-surface-900 dark:text-white">{data.agents.total}</span>
              </div>
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Ativos</span>
                <span className="font-mono font-medium text-green-600 dark:text-green-400">{data.agents.active}</span>
              </div>
              <div className="flex justify-between text-surface-600 dark:text-surface-400">
                <span>Offline</span>
                <span className="font-mono font-medium text-red-600">{data.agents.offline}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
