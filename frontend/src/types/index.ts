// netguard/frontend/src/types/index.ts

// === Auth ===
export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginRequest {
  username: string
  password: string
}

// === User ===
export type UserRole = 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  is_superuser: boolean
  avatar_url?: string
  last_login?: string
  created_at: string
  updated_at: string
}

export interface UserCreate {
  username: string
  email: string
  full_name: string
  password: string
  role: UserRole
}

// === Device ===
export type DeviceType =
  | 'switch' | 'router' | 'firewall' | 'server' | 'desktop'
  | 'printer' | 'access_point' | 'ip_phone' | 'camera' | 'iot' | 'unknown'

export type DeviceStatus = 'online' | 'offline' | 'unreachable'

export interface Device {
  id: string
  ip_address: string
  mac_address?: string
  hostname?: string
  fqdn?: string
  device_type: DeviceType
  status: DeviceStatus
  vendor?: string
  model?: string
  os_name?: string
  os_version?: string
  image_url?: string
  snmp_enabled: boolean
  snmp_version?: string
  snmp_sys_descr?: string
  snmp_sys_name?: string
  snmp_sys_location?: string
  snmp_sys_contact?: string
  snmp_sys_uptime?: string
  snmp_sys_object_id?: string
  network_segment?: string
  open_ports?: number[]
  is_visible: boolean
  is_pinned: boolean
  tags: string[]
  cpu_usage?: number
  memory_usage?: number
  disk_usage?: number
  first_seen: string
  last_seen: string
  created_at: string
}

export interface DeviceSummary {
  total_devices: number
  online: number
  offline: number
  snmp_active: number
  snmp_inactive: number
  by_type: Record<string, number>
  new_last_24h: number
}

// === Scan ===
export type ScanType = 'discovery' | 'port_scan' | 'vulnerability' | 'pentest' | 'snmp_collection' | 'full'
export type ScanStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface ScanJob {
  id: string
  name: string
  scan_type: ScanType
  status: ScanStatus
  target: string
  target_ports?: string
  celery_task_id?: string
  progress: number
  devices_found: number
  vulnerabilities_found: number
  results_summary?: Record<string, unknown>
  error_message?: string
  is_scheduled: boolean
  schedule_cron?: string
  options?: Record<string, unknown>
  next_run?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

export interface ScanJobCreate {
  name: string
  scan_type: ScanType
  target: string
  target_ports?: string
  options?: Record<string, unknown>
  is_scheduled?: boolean
  schedule_cron?: string
  schedule_frequency?: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'custom'
  schedule_time?: string
  schedule_days?: number[]
  schedule_day_of_month?: number
}

// === Vulnerability ===
export interface Vulnerability {
  id: string
  device_id: string
  title: string
  description?: string
  severity: SeverityLevel
  cvss_score?: number
  cve_id?: string
  cve_description?: string
  port?: number
  protocol?: string
  service_name?: string
  service_version?: string
  remediation?: string
  remediation_effort?: string
  fix_available: boolean
  is_false_positive: boolean
  is_resolved: boolean
  evidence?: Record<string, unknown>
  first_detected: string
  last_detected: string
}

export interface VulnerabilitySummary {
  total: number
  critical: number
  high: number
  medium: number
  low: number
  info: number
  resolved: number
  false_positives: number
}

// === Alert ===
export type AlertStatus = 'active' | 'acknowledged' | 'muted' | 'resolved'

export interface Alert {
  id: string
  device_id?: string
  title: string
  message?: string
  severity: string
  category: string
  status: AlertStatus
  is_muted: boolean
  muted_until?: string
  muted_reason?: string
  occurrence_count: number
  triggered_at: string
  last_occurrence: string
  acknowledged_at?: string
  resolved_at?: string
  details?: Record<string, unknown>
}

export interface AlertSummary {
  total_active: number
  critical: number
  high: number
  medium: number
  low: number
  muted: number
  acknowledged: number
  device_offline: number
  agent_offline: number
}

// === Dashboard ===
export interface DashboardOverview {
  devices: {
    total: number
    online: number
    offline: number
    snmp_active: number
    snmp_inactive: number
    new_last_24h: number
    by_type: Record<string, number>
  }
  scans: {
    active: number
    last_week: number
  }
  vulnerabilities: {
    total_open: number
    by_severity: Record<string, number>
  }
  alerts: {
    active: number
    critical: number
    muted: number
  }
  agents: {
    total: number
    active: number
    offline: number
  }
}

// === Paginated Response ===
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// === SNMP ===
export interface SNMPCommunity {
  id: string
  name: string
  community_string: string
  snmp_version: string
  description?: string
  is_default: boolean
  is_active: boolean
  created_at: string
}

export interface SNMPInterface {
  id: string
  device_id: string
  if_index: number
  if_name?: string
  if_descr?: string
  if_alias?: string
  if_speed?: number
  if_high_speed?: number
  if_admin_status?: number
  if_oper_status?: number
  if_in_octets: number
  if_out_octets: number
  if_in_errors: number
  if_out_errors: number
  if_in_discards?: number
  if_out_discards?: number
  in_error_rate?: number
  out_error_rate?: number
  in_bps?: number
  out_bps?: number
  utilization_in?: number
  utilization_out?: number
  last_collected?: string
}
