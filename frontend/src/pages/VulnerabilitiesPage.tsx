// netguard/frontend/src/pages/VulnerabilitiesPage.tsx
import { useEffect, useState } from 'react'
import { scansApi } from '@/services/api'
import type { Vulnerability, VulnerabilitySummary } from '@/types'
import { cn, formatDate, severityColor } from '@/lib/utils'
import { Shield, ChevronRight, ExternalLink } from 'lucide-react'

export function VulnerabilitiesPage() {
  const [vulns, setVulns] = useState<Vulnerability[]>([])
  const [summary, setSummary] = useState<VulnerabilitySummary | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [severity, setSeverity] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const pageSize = 20

  const fetchVulns = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize, is_resolved: false }
      if (severity) params.severity = severity
      const [vulnRes, sumRes] = await Promise.all([
        scansApi.vulnerabilities(params),
        scansApi.vulnerabilitySummary(),
      ])
      setVulns(vulnRes.data.items)
      setTotal(vulnRes.data.total)
      setSummary(sumRes.data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchVulns() }, [page, severity])

  const totalPages = Math.ceil(total / pageSize)

  const sevCards = [
    { key: 'critical', label: 'Critical', color: 'bg-red-500', count: summary?.critical || 0 },
    { key: 'high', label: 'High', color: 'bg-orange-500', count: summary?.high || 0 },
    { key: 'medium', label: 'Medium', color: 'bg-yellow-500', count: summary?.medium || 0 },
    { key: 'low', label: 'Low', color: 'bg-blue-500', count: summary?.low || 0 },
    { key: 'info', label: 'Info', color: 'bg-gray-400', count: summary?.info || 0 },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-surface-900 dark:text-white">Vulnerabilidades</h1>
        <p className="text-sm text-surface-500 mt-0.5">{summary?.total || 0} total · {summary?.resolved || 0} resolvidas</p>
      </div>

      {/* Severity cards */}
      <div className="grid grid-cols-5 gap-3">
        {sevCards.map((s) => (
          <button key={s.key} onClick={() => { setSeverity(severity === s.key ? '' : s.key); setPage(1) }}
            className={cn('card-padded text-center transition-all', severity === s.key && 'ring-2 ring-brand-500')}>
            <div className={cn('w-3 h-3 rounded-full mx-auto mb-2', s.color)} />
            <p className="text-xl font-bold text-surface-900 dark:text-white">{s.count}</p>
            <p className="text-xs text-surface-500">{s.label}</p>
          </button>
        ))}
      </div>

      {/* Vulnerability list */}
      <div className="space-y-2">
        {loading ? (
          <div className="card-padded text-center text-surface-400 py-12">Carregando...</div>
        ) : vulns.length === 0 ? (
          <div className="card-padded text-center py-12">
            <Shield className="w-10 h-10 mx-auto mb-3 text-green-500 opacity-60" />
            <p className="text-surface-500">Nenhuma vulnerabilidade encontrada</p>
          </div>
        ) : vulns.map((v) => {
          const isExp = expanded === v.id
          return (
            <div key={v.id} className="card overflow-hidden">
              <button onClick={() => setExpanded(isExp ? null : v.id)}
                className="w-full flex items-center gap-3 px-5 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 text-left">
                <ChevronRight className={cn('w-4 h-4 text-surface-400 transition-transform', isExp && 'rotate-90')} />
                <span className={severityColor(v.severity)}>{v.severity.toUpperCase()}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-surface-900 dark:text-white truncate">{v.title}</p>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-surface-500">
                    {v.cve_id && <span className="font-mono text-brand-600 dark:text-brand-400">{v.cve_id}</span>}
                    {v.service_name && <span>Serviço: {v.service_name}</span>}
                    {v.port && <span>Porta: {v.port}</span>}
                    {v.cvss_score && <span>CVSS: {v.cvss_score}</span>}
                  </div>
                </div>
                <span className="text-xs text-surface-400 shrink-0">{formatDate(v.last_detected)}</span>
              </button>

              {isExp && (
                <div className="border-t border-surface-200 dark:border-surface-700 px-5 py-4 bg-surface-50/50 dark:bg-surface-800/30 space-y-3">
                  {v.description && (
                    <div><span className="label">Descrição</span><p className="text-sm text-surface-700 dark:text-surface-300">{v.description}</p></div>
                  )}
                  {v.service_version && (
                    <div><span className="label">Versão do serviço</span><p className="text-sm font-mono text-surface-700 dark:text-surface-300">{v.service_version}</p></div>
                  )}
                  {v.remediation && (
                    <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                      <span className="text-xs font-semibold text-green-700 dark:text-green-400">Remediação sugerida</span>
                      <p className="text-sm text-green-800 dark:text-green-300 mt-1">{v.remediation}</p>
                    </div>
                  )}
                  {v.cve_id && (
                    <a href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-brand-600 hover:underline">
                      Ver {v.cve_id} no NVD <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary btn-sm">Anterior</button>
          <span className="text-sm text-surface-500">Página {page} de {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary btn-sm">Próxima</button>
        </div>
      )}
    </div>
  )
}
