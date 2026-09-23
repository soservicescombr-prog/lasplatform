// netguard/frontend/src/pages/UsersPage.tsx
import { useEffect, useState } from 'react'
import { usersApi, authApi } from '@/services/api'
import type { User } from '@/types'
import { cn, formatDate } from '@/lib/utils'
import { Plus, Trash2, Edit2, Loader2, X } from 'lucide-react'
import toast from 'react-hot-toast'

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', full_name: '', password: '', role: 'viewer' })
  const [submitting, setSubmitting] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<{ role: string; is_active: boolean }>({ role: 'viewer', is_active: true })

  const fetchUsers = async () => {
    try {
      const { data } = await usersApi.list({ page_size: 100 })
      setUsers(data.items)
      setTotal(data.total)
    } catch { toast.error('Erro ao carregar usuários') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchUsers() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await authApi.register(form)
      toast.success('Usuário criado')
      setShowForm(false)
      setForm({ username: '', email: '', full_name: '', password: '', role: 'viewer' })
      fetchUsers()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Erro ao criar')
    } finally { setSubmitting(false) }
  }

  const handleEdit = async (id: string) => {
    try {
      await usersApi.update(id, editForm)
      toast.success('Usuário atualizado')
      setEditingId(null)
      fetchUsers()
    } catch { toast.error('Erro') }
  }

  const handleDeactivate = async (id: string) => {
    if (!confirm('Desativar este usuário?')) return
    try {
      await usersApi.delete(id)
      toast.success('Usuário desativado')
      fetchUsers()
    } catch (err: any) { toast.error(err?.response?.data?.detail || 'Erro') }
  }

  const roleColors: Record<string, string> = {
    admin: 'bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400',
    operator: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    viewer: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Usuários</h1>
          <p className="text-sm text-surface-500 mt-0.5">{total} usuários cadastrados</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="w-4 h-4" /> Novo usuário
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleCreate} className="card-padded space-y-4">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Criar novo usuário</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Usuário</label>
              <input className="input" placeholder="johndoe" value={form.username}
                onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))} required /></div>
            <div><label className="label">E-mail</label>
              <input className="input" type="email" placeholder="john@empresa.com" value={form.email}
                onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))} required /></div>
            <div><label className="label">Nome completo</label>
              <input className="input" placeholder="John Doe" value={form.full_name}
                onChange={(e) => setForm(f => ({ ...f, full_name: e.target.value }))} required /></div>
            <div><label className="label">Senha</label>
              <input className="input" type="password" placeholder="Min. 6 caracteres" value={form.password}
                onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))} required minLength={6} /></div>
            <div><label className="label">Papel</label>
              <select className="input" value={form.role}
                onChange={(e) => setForm(f => ({ ...f, role: e.target.value }))}>
                <option value="viewer">Visualizador</option>
                <option value="operator">Operador</option>
                <option value="admin">Administrador</option>
              </select></div>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Criar
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      )}

      {/* User table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <th className="text-left px-5 py-3 font-medium text-surface-500">Usuário</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Nome</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">E-mail</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Papel</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Status</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Último login</th>
              <th className="text-right px-5 py-3 font-medium text-surface-500">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-surface-400">Carregando...</td></tr>
            ) : users.map((u) => (
              <tr key={u.id} className="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/30">
                <td className="px-5 py-3 font-medium font-mono text-surface-900 dark:text-white">{u.username}</td>
                <td className="px-5 py-3 text-surface-700 dark:text-surface-300">{u.full_name}</td>
                <td className="px-5 py-3 text-surface-500">{u.email}</td>
                <td className="px-5 py-3">
                  {editingId === u.id ? (
                    <select className="input w-auto py-0.5 text-xs" value={editForm.role}
                      onChange={(e) => setEditForm(f => ({ ...f, role: e.target.value }))}>
                      <option value="viewer">Visualizador</option>
                      <option value="operator">Operador</option>
                      <option value="admin">Administrador</option>
                    </select>
                  ) : (
                    <span className={cn('badge text-2xs uppercase tracking-wide', roleColors[u.role])}>{u.role}</span>
                  )}
                </td>
                <td className="px-5 py-3">
                  <span className={cn('badge text-2xs', u.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'badge-info')}>
                    {u.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                </td>
                <td className="px-5 py-3 text-xs text-surface-400">{u.last_login ? formatDate(u.last_login) : '—'}</td>
                <td className="px-5 py-3 text-right">
                  {editingId === u.id ? (
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => handleEdit(u.id)} className="btn-primary btn-sm">Salvar</button>
                      <button onClick={() => setEditingId(null)} className="btn-ghost btn-sm"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ) : (
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => { setEditingId(u.id); setEditForm({ role: u.role, is_active: u.is_active }) }}
                        className="btn-ghost btn-sm" title="Editar"><Edit2 className="w-3.5 h-3.5" /></button>
                      {!u.is_superuser && (
                        <button onClick={() => handleDeactivate(u.id)} className="btn-ghost btn-sm text-red-500" title="Desativar">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
