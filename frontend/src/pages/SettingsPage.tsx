// netguard/frontend/src/pages/SettingsPage.tsx
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { authApi } from '@/services/api'
import { cn } from '@/lib/utils'
import { Settings, Moon, Sun, Lock, Info, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

export function SettingsPage() {
  const { user } = useAuthStore()
  const { darkMode, toggleDarkMode } = useThemeStore()
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm: '' })
  const [saving, setSaving] = useState(false)

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (passwords.new_password !== passwords.confirm) {
      toast.error('As senhas não coincidem')
      return
    }
    if (passwords.new_password.length < 6) {
      toast.error('Senha deve ter ao menos 6 caracteres')
      return
    }
    setSaving(true)
    try {
      await authApi.changePassword(passwords.current_password, passwords.new_password)
      toast.success('Senha alterada com sucesso')
      setPasswords({ current_password: '', new_password: '', confirm: '' })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erro ao alterar senha')
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-surface-900 dark:text-white">Configurações</h1>
        <p className="text-sm text-surface-500 mt-0.5">Preferências e segurança da conta</p>
      </div>

      {/* Profile info */}
      <div className="card-padded space-y-4">
        <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <Info className="w-4 h-4" /> Informações do perfil
        </h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="label">Usuário</span>
            <p className="text-surface-900 dark:text-white font-mono">{user?.username}</p>
          </div>
          <div>
            <span className="label">Nome</span>
            <p className="text-surface-900 dark:text-white">{user?.full_name}</p>
          </div>
          <div>
            <span className="label">E-mail</span>
            <p className="text-surface-900 dark:text-white">{user?.email}</p>
          </div>
          <div>
            <span className="label">Papel</span>
            <span className={cn(
              'badge text-xs uppercase',
              user?.role === 'admin' ? 'bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400' :
              user?.role === 'operator' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
              'badge-info'
            )}>
              {user?.role}
            </span>
          </div>
        </div>
      </div>

      {/* Theme */}
      <div className="card-padded">
        <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2 mb-3">
          {darkMode ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />} Aparência
        </h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-surface-900 dark:text-white">Modo escuro</p>
            <p className="text-xs text-surface-500">Tema dark para reduzir cansaço visual</p>
          </div>
          <button onClick={toggleDarkMode}
            className={cn(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
              darkMode ? 'bg-brand-600' : 'bg-surface-300',
            )}>
            <span className={cn(
              'inline-block h-4 w-4 rounded-full bg-white transition-transform',
              darkMode ? 'translate-x-6' : 'translate-x-1',
            )} />
          </button>
        </div>
      </div>

      {/* Change password */}
      <form onSubmit={handleChangePassword} className="card-padded space-y-4">
        <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <Lock className="w-4 h-4" /> Alterar senha
        </h2>
        <div className="space-y-3">
          <div>
            <label className="label">Senha atual</label>
            <input type="password" className="input" value={passwords.current_password}
              onChange={(e) => setPasswords(p => ({ ...p, current_password: e.target.value }))} required />
          </div>
          <div>
            <label className="label">Nova senha</label>
            <input type="password" className="input" value={passwords.new_password}
              onChange={(e) => setPasswords(p => ({ ...p, new_password: e.target.value }))} required minLength={6} />
          </div>
          <div>
            <label className="label">Confirmar nova senha</label>
            <input type="password" className="input" value={passwords.confirm}
              onChange={(e) => setPasswords(p => ({ ...p, confirm: e.target.value }))} required minLength={6} />
          </div>
        </div>
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />} Alterar senha
        </button>
      </form>

      {/* System info */}
      <div className="card-padded">
        <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2 mb-3">
          <Settings className="w-4 h-4" /> Sistema
        </h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-surface-600 dark:text-surface-400">
            <span>Versão</span>
            <span className="font-mono text-surface-900 dark:text-white">NetGuard v1.0.0</span>
          </div>
          <div className="flex justify-between text-surface-600 dark:text-surface-400">
            <span>API</span>
            <span className="font-mono text-surface-900 dark:text-white">/api/v1</span>
          </div>
          <div className="flex justify-between text-surface-600 dark:text-surface-400">
            <span>Documentação API</span>
            <a href="/docs" target="_blank" className="text-brand-600 hover:underline">/docs (Swagger)</a>
          </div>
        </div>
      </div>
    </div>
  )
}
