// netguard/frontend/src/pages/ThreatIntelPage.tsx
import { useState } from 'react'
import api from '@/services/api'
import { cn } from '@/lib/utils'
import { Globe, Search, Loader2, AlertTriangle, Shield, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'

export function ThreatIntelPage() {
  const [ipQuery, setIpQuery] = useState('')
  const [cveQuery, setCveQuery] = useState('')
  const [ipResult, setIpResult] = useState<Record<string, unknown> | null>(null)
  const [cveResult, setCveResult] = useState<Record<string, unknown> | null>(null)
  const [threats, setThreats] = useState<unknown[]>([])
  const [loading, setLoading] = useState('')

  const checkIP = async () => {
    if (!ipQuery) return
    setLoading('ip')
    try {
      const { data } = await api.get(`/extras/threat-intel/ip/${ipQuery}`)
      setIpResult(data)
    } catch { toast.error('Erro na consulta') }
    finally { setLoading('') }
  }

  const checkCVE = async () => {
    if (!cveQuery) return
    setLoading('cve')
    try {
      const { data } = await api.get(`/extras/threat-intel/cve/${cveQuery}`)
      setCveResult(data)
    } catch { toast.error('Erro na consulta') }
    finally { setLoading('') }
  }

  const loadLatest = async () => {
    setLoading('latest')
    try {
      const { data } = await api.get('/extras/threat-intel/latest', { params: { limit: 15 } })
      setThreats(data)
    } catch { toast.error('Erro ao carregar. Configure OTX_API_KEY.') }
    finally { setLoading('') }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-surface-900 dark:text-white">Threat Intelligence</h1>
        <p className="text-sm text-surface-500 mt-0.5">Consulta de reputação de IPs e CVEs via AlienVault OTX e NVD</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* IP Check */}
        <div className="card-padded space-y-3">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Verificar IP</h2>
          <div className="flex gap-2">
            <input className="input flex-1 font-mono" placeholder="Ex: 185.220.101.1" value={ipQuery}
              onChange={e => setIpQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && checkIP()} />
            <button onClick={checkIP} disabled={loading === 'ip'} className="btn-primary">
              {loading === 'ip' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </button>
          </div>
          {ipResult && (
            <div className={cn('rounded-lg p-3 text-sm', (ipResult as any).is_malicious ? 'bg-red-50 dark:bg-red-900/20' : 'bg-green-50 dark:bg-green-900/20')}>
              <div className="flex items-center gap-2 mb-2">
                {(ipResult as any).is_malicious
                  ? <AlertTriangle className="w-5 h-5 text-red-500" />
                  : <Shield className="w-5 h-5 text-green-500" />}
                <span className={cn('font-semibold', (ipResult as any).is_malicious ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400')}>
                  {(ipResult as any).is_malicious ? 'IP MALICIOSO' : 'IP Limpo'}
                </span>
                <span className="text-xs text-surface-500 ml-auto">Score: {(ipResult as any).threat_score || 0}/100</span>
              </div>
              {((ipResult as any).sources as string[])?.length > 0 && (
                <p className="text-xs text-surface-500">Fontes: {((ipResult as any).sources as string[]).join(', ')}</p>
              )}
            </div>
          )}
        </div>

        {/* CVE Check */}
        <div className="card-padded space-y-3">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Consultar CVE</h2>
          <div className="flex gap-2">
            <input className="input flex-1 font-mono" placeholder="Ex: CVE-2024-3094" value={cveQuery}
              onChange={e => setCveQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && checkCVE()} />
            <button onClick={checkCVE} disabled={loading === 'cve'} className="btn-primary">
              {loading === 'cve' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </button>
          </div>
          {cveResult && (cveResult as any).nvd && (
            <div className="bg-surface-50 dark:bg-surface-800 rounded-lg p-3 text-sm space-y-2">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-brand-600">{(cveResult as any).cve_id}</span>
                {(cveResult as any).nvd.cvss_score && (
                  <span className={cn('badge font-bold',
                    (cveResult as any).nvd.cvss_score >= 9 ? 'badge-critical' :
                    (cveResult as any).nvd.cvss_score >= 7 ? 'badge-high' : 'badge-medium'
                  )}>CVSS {(cveResult as any).nvd.cvss_score}</span>
                )}
              </div>
              <p className="text-xs text-surface-600 dark:text-surface-400">{((cveResult as any).nvd.description as string)?.substring(0, 300)}</p>
              {(cveResult as any).nvd.references?.slice(0, 3).map((ref: string, i: number) => (
                <a key={i} href={ref} target="_blank" rel="noopener noreferrer"
                  className="block text-xs text-brand-600 hover:underline truncate">
                  <ExternalLink className="w-3 h-3 inline mr-1" />{ref}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Latest Threats */}
      <div className="card-padded">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <Globe className="w-4 h-4" /> Últimas ameaças (AlienVault OTX)
          </h2>
          <button onClick={loadLatest} disabled={loading === 'latest'} className="btn-secondary btn-sm">
            {loading === 'latest' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Carregar'}
          </button>
        </div>
        {(threats as any[]).length > 0 ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(threats as any[]).map((t, i) => (
              <div key={i} className="border-b border-surface-100 dark:border-surface-800 pb-2">
                <p className="text-sm font-medium text-surface-900 dark:text-white">{t.name}</p>
                <p className="text-xs text-surface-500 mt-0.5 line-clamp-2">{t.description}</p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  {t.tags?.slice(0, 5).map((tag: string, j: number) => (
                    <span key={j} className="badge-info text-2xs">{tag}</span>
                  ))}
                  <span className="text-2xs text-surface-400 ml-auto">{t.indicators_count} IoCs</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-surface-400 text-center py-4">Clique em "Carregar" (requer OTX_API_KEY configurada)</p>
        )}
      </div>
    </div>
  )
}
