// netguard/frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { DevicesPage } from '@/pages/DevicesPage'
import { DiscoveryPage } from '@/pages/DiscoveryPage'
import { SNMPPage } from '@/pages/SNMPPage'
import { VulnerabilitiesPage } from '@/pages/VulnerabilitiesPage'
import { PentestPage } from '@/pages/PentestPage'
import { AlertsPage } from '@/pages/AlertsPage'
import { AgentsPage } from '@/pages/AgentsPage'
import { UsersPage } from '@/pages/UsersPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { TopologyPage } from '@/pages/TopologyPage'
import { InventoryPage } from '@/pages/InventoryPage'
import { CompliancePage } from '@/pages/CompliancePage'
import { ThreatIntelPage } from '@/pages/ThreatIntelPage'
import { SyslogPage } from '@/pages/SyslogPage'
import { TasksPage } from '@/pages/TasksPage'
import { AgentDetailsPage } from '@/pages/AgentDetailsPage'
import { DeviceDetailsPage } from '@/pages/DeviceDetailsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="devices/:id" element={<DeviceDetailsPage />} />
        <Route path="topology" element={<TopologyPage />} />
        <Route path="discovery" element={<DiscoveryPage />} />
        <Route path="snmp" element={<SNMPPage />} />
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="vulnerabilities" element={<VulnerabilitiesPage />} />
        <Route path="pentest" element={<PentestPage />} />
        <Route path="compliance" element={<CompliancePage />} />
        <Route path="threat-intel" element={<ThreatIntelPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="syslog" element={<SyslogPage />} />
        <Route path="logs" element={<SyslogPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="agents/:id" element={<AgentDetailsPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
