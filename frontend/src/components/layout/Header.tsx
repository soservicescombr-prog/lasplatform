// netguard/frontend/src/components/layout/Header.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import {
  Bell,
  Search,
  Moon,
  Sun,
  LogOut,
  User,
  ChevronDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function Header() {
  const { user, logout } = useAuthStore()
  const { darkMode, toggleDarkMode } = useThemeStore()
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/devices?search=${encodeURIComponent(searchQuery)}`)
      setSearchQuery('')
    }
  }

  return (
    <header className="h-14 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 flex items-center justify-between px-6 sticky top-0 z-20">
      {/* Search */}
      <form onSubmit={handleSearch} className="relative w-80">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
        <input
          type="text"
          placeholder="Buscar dispositivo, IP, hostname..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input pl-10 py-1.5 text-sm"
        />
      </form>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          onClick={toggleDarkMode}
          className="btn-ghost btn-sm p-2 rounded-lg"
          title={darkMode ? 'Modo claro' : 'Modo escuro'}
        >
          {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Notifications */}
        <button
          onClick={() => navigate('/alerts')}
          className="btn-ghost btn-sm p-2 rounded-lg relative"
          title="Alertas"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>

        {/* Profile dropdown */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-brand-100 dark:bg-brand-900 flex items-center justify-center">
              <User className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            </div>
            <span className="text-sm font-medium text-surface-700 dark:text-surface-300 max-w-[120px] truncate">
              {user?.full_name || user?.username}
            </span>
            <ChevronDown className="w-3 h-3 text-surface-400" />
          </button>

          {profileOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setProfileOpen(false)} />
              <div className="absolute right-0 top-full mt-1 w-56 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 py-1 z-50">
                <div className="px-3 py-2 border-b border-surface-200 dark:border-surface-700">
                  <p className="text-sm font-medium text-surface-900 dark:text-white">
                    {user?.full_name}
                  </p>
                  <p className="text-xs text-surface-500">{user?.email}</p>
                  <span className={cn(
                    'inline-block mt-1 text-2xs px-1.5 py-0.5 rounded font-medium uppercase tracking-wide',
                    user?.role === 'admin' ? 'bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-400'
                      : 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
                  )}>
                    {user?.role}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sair
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
