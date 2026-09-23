// netguard/frontend/src/components/layout/Sidebar.tsx
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard, Network, Radar, Shield, Bug, Crosshair, Bell, Users,
  Settings, ChevronLeft, Activity, Map, Package, ShieldCheck, Globe,
  ScrollText, ListTodo,
} from 'lucide-react'
import { useState } from 'react'

interface NavItem { label: string; path: string; icon: React.ElementType; section?: string }

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, section: 'main' },
  { label: 'Dispositivos', path: '/devices', icon: Network, section: 'rede' },
  { label: 'Topologia', path: '/topology', icon: Map, section: 'rede' },
  { label: 'Discovery', path: '/discovery', icon: Radar, section: 'rede' },
  { label: 'SNMP', path: '/snmp', icon: Activity, section: 'rede' },
  { label: 'Inventário', path: '/inventory', icon: Package, section: 'rede' },
  { label: 'Vulnerabilidades', path: '/vulnerabilities', icon: Bug, section: 'segurança' },
  { label: 'Pentest', path: '/pentest', icon: Crosshair, section: 'segurança' },
  { label: 'Compliance', path: '/compliance', icon: ShieldCheck, section: 'segurança' },
  { label: 'Threat Intel', path: '/threat-intel', icon: Globe, section: 'segurança' },
  { label: 'Alertas', path: '/alerts', icon: Bell, section: 'ops' },
  { label: 'Logs', path: '/logs', icon: ScrollText, section: 'ops' },
  { label: 'Agentes', path: '/agents', icon: Shield, section: 'ops' },
  { label: 'Tasks', path: '/tasks', icon: ListTodo, section: 'ops' },
  { label: 'Usuários', path: '/users', icon: Users, section: 'admin' },
  { label: 'Configurações', path: '/settings', icon: Settings, section: 'admin' },
]

const sections = [
  { key: 'main', label: '' },
  { key: 'rede', label: 'Rede' },
  { key: 'segurança', label: 'Segurança' },
  { key: 'ops', label: 'Operações' },
  { key: 'admin', label: 'Administração' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside className={cn(
      'fixed left-0 top-0 z-30 h-screen border-r border-surface-200 dark:border-surface-700',
      'bg-white dark:bg-surface-900 flex flex-col transition-all duration-200',
      collapsed ? 'w-16' : 'w-[260px]',
    )}>
      {/* Logo */}
      <div className="flex items-center gap-3 h-14 px-4 border-b border-surface-200 dark:border-surface-700 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center shrink-0">
          <Shield className="w-5 h-5 text-white" />
        </div>
        {!collapsed && <span className="font-bold text-lg tracking-tight text-surface-900 dark:text-white">NetGuard</span>}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {sections.map((section) => {
          const items = navItems.filter(i => i.section === section.key)
          if (items.length === 0) return null
          return (
            <div key={section.key} className="mb-1">
              {section.label && !collapsed && (
                <p className="text-2xs font-semibold text-surface-400 uppercase tracking-wider px-3 pt-3 pb-1">{section.label}</p>
              )}
              {collapsed && section.label && <div className="border-t border-surface-200 dark:border-surface-700 my-1 mx-2" />}
              <ul className="space-y-0.5">
                {items.map((item) => (
                  <li key={item.path}>
                    <NavLink to={item.path} end={item.path === '/'}
                      className={({ isActive }) => cn(
                        'flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors',
                        isActive ? 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-400 font-medium'
                          : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800',
                        collapsed && 'justify-center px-0',
                      )}
                      title={collapsed ? item.label : undefined}>
                      <item.icon className="w-4.5 h-4.5 shrink-0" style={{ width: 18, height: 18 }} />
                      {!collapsed && <span className="text-[13px]">{item.label}</span>}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </nav>

      <button onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-surface-200 dark:border-surface-700 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300">
        <ChevronLeft className={cn('w-4 h-4 transition-transform', collapsed && 'rotate-180')} />
      </button>
    </aside>
  )
}
