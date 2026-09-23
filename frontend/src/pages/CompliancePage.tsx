// netguard/frontend/src/pages/CompliancePage.tsx
import { useState } from 'react'
import api from '@/services/api'
import { cn } from '@/lib/utils'
import { ShieldCheck, Play, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'

interface Finding { check_id: string; category: string; title: string; description: string; severity: string; status: string; device_ip: string; device_hostname?: string; remediation?: string }

export function CompliancePage() {
  const [result, setResult] = useState<{ score: number; total_checks: number; passed: number; failed: number; findings: Finding[] } | null>(null)
  const [loading, setLoading] = useState(false)

  const runCheck = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/extras/compliance/check')
      setResult(data)
      toast.success(`Compliance check concluído: ${data.score}%`)
    } catch { toast.error('Erro ao executar') }
    finally { setLoading(false) }
  }

  const scoreColor = (score: number) =>
    score >= 80 ? 'text-green-500' : score >= 60 ? 'text-yellow-500' : 'text-red-500'

  const failed = result?.findings.filter(f => f.status === 'fail') || []
  const passed = result?.findings.filter(f => f.status === 'pass') || []

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Compliance Checker</h1>
          <p className="text-sm text-surface-500 mt-0.5">Verificação CIS Benchmark e PCI-DSS</p>
        </div>
        <button onClick={runCheck} disabled={loading} className="btn-primary">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Executar verificação
        </button>
      </div>

      {result && (
        <>
          {/* Score card */}
          <div className="grid grid-cols-4 gap-4">
            <div className="card-padded text-center col-span-1">
              <p className={cn('text-5xl font-bold', scoreColor(result.score))}>{result.score}%</p>
              <p className="text-sm text-surface-500 mt-1">Score geral</p>
            </div>
            <div className="card-padded text-center">
              <p className="text-2xl font-bold text-surface-900 dark:text-white">{result.total_checks}</p>
              <p className="text-sm text-surface-500">Total de checks</p>
            </div>
            <div className="card-padded text-center">
              <p className="text-2xl font-bold text-green-500">{result.passed}</p>
              <p className="text-sm text-surface-500">Aprovados</p>
            </div>
            <div className="card-padded text-center">
              <p className="text-2xl font-bold text-red-500">{result.failed}</p>
              <p className="text-sm text-surface-500">Reprovados</p>
            </div>
          </div>

          {/* Failed checks */}
          {failed.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
                <XCircle className="w-4 h-4" /> Não conforme ({failed.length})
              </h2>
              {failed.map((f, i) => (
                <div key={i} className="card border-l-4 border-l-red-500 px-5 py-3">
                  <div className="flex items-start gap-3">
                    <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="badge-info text-2xs font-mono">{f.check_id}</span>
                        <span className={cn('badge text-2xs', f.severity === 'critical' ? 'badge-critical' : f.severity === 'high' ? 'badge-high' : 'badge-medium')}>{f.severity}</span>
                      </div>
                      <p className="font-medium text-surface-900 dark:text-white mt-1">{f.title}</p>
                      <p className="text-xs text-surface-500 mt-0.5">{f.description}</p>
                      <p className="text-xs text-surface-400 mt-0.5">Dispositivo: {f.device_ip}</p>
                      {f.remediation && (
                        <div className="mt-2 bg-green-50 dark:bg-green-900/20 rounded p-2 text-xs text-green-800 dark:text-green-300">
                          <strong>Remediação:</strong> {f.remediation}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Passed checks */}
          {passed.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-green-600 dark:text-green-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> Conforme ({passed.length})
              </h2>
              {passed.slice(0, 20).map((f, i) => (
                <div key={i} className="card px-5 py-2 flex items-center gap-3">
                  <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                  <span className="badge-info text-2xs font-mono">{f.check_id}</span>
                  <span className="text-sm text-surface-700 dark:text-surface-300">{f.title}</span>
                  <span className="text-xs text-surface-400 ml-auto">{f.device_ip}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div className="card-padded text-center py-16">
          <ShieldCheck className="w-12 h-12 mx-auto mb-3 text-surface-300 dark:text-surface-600" />
          <p className="text-surface-500">Clique em "Executar verificação" para analisar a conformidade da sua rede</p>
          <p className="text-xs text-surface-400 mt-1">Checks baseados em CIS Benchmarks e PCI-DSS</p>
        </div>
      )}
    </div>
  )
}
