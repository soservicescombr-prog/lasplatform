// netguard/frontend/src/services/api.ts
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/authStore'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach JWT
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor — handle 401 / token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = useAuthStore.getState().refreshToken
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          return api(originalRequest)
        } catch {
          useAuthStore.getState().logout()
          window.location.href = '/login'
        }
      } else {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  },
)

// === Auth ===
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
  me: () => api.get('/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),
  register: (data: Record<string, unknown>) =>
    api.post('/auth/register', data),
}

// === Users ===
export const usersApi = {
  list: (params?: Record<string, unknown>) => api.get('/users', { params }),
  get: (id: string) => api.get(`/users/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
}

// === Devices ===
export const devicesApi = {
  list: (params?: Record<string, unknown>) => api.get('/devices', { params }),
  get: (id: string) => api.get(`/devices/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/devices/${id}`, data),
  delete: (id: string) => api.delete(`/devices/${id}`),
  pin: (id: string) => api.post(`/devices/${id}/pin`),
  summary: () => api.get('/devices/summary'),
  details: (id: string, hours = 24) => api.get(`/devices/${id}/details`, { params: { hours } }),
}

// === Scans ===
export const scansApi = {
  create: (data: Record<string, unknown>) => api.post('/scans', data),
  list: (params?: Record<string, unknown>) => api.get('/scans', { params }),
  get: (id: string) => api.get(`/scans/${id}`),
  executorHealth: () => api.get('/scans/executor/health'),
  cancel: (id: string) => api.post(`/scans/${id}/cancel`),
  disableSchedule: (id: string) => api.post(`/scans/${id}/schedule/disable`),
  vulnerabilities: (params?: Record<string, unknown>) =>
    api.get('/scans/vulnerabilities/all', { params }),
  vulnerabilitySummary: () => api.get('/scans/vulnerabilities/summary'),
}

// === Alerts ===
export const alertsApi = {
  list: (params?: Record<string, unknown>) => api.get('/alerts', { params }),
  summary: () => api.get('/alerts/summary'),
  mute: (id: string, data?: Record<string, unknown>) => api.post(`/alerts/${id}/mute`, data),
  unmute: (id: string) => api.post(`/alerts/${id}/unmute`),
  acknowledge: (id: string, data?: Record<string, unknown>) =>
    api.post(`/alerts/${id}/acknowledge`, data),
  resolve: (id: string) => api.post(`/alerts/${id}/resolve`),
  rules: () => api.get('/alerts/rules'),
  createRule: (data: Record<string, unknown>) => api.post('/alerts/rules', data),
  updateRule: (id: string, data: Record<string, unknown>) =>
    api.put(`/alerts/rules/${id}`, data),
  deleteRule: (id: string) => api.delete(`/alerts/rules/${id}`),
}

// === SNMP ===
export const snmpApi = {
  communities: () => api.get('/snmp/communities'),
  createCommunity: (data: Record<string, unknown>) => api.post('/snmp/communities', data),
  updateCommunity: (id: string, data: Record<string, unknown>) =>
    api.put(`/snmp/communities/${id}`, data),
  deleteCommunity: (id: string) => api.delete(`/snmp/communities/${id}`),
  collect: (data: Record<string, unknown>) => api.post('/snmp/collect', data),
  interfaces: (deviceId: string) => api.get(`/snmp/interfaces/${deviceId}`),
  history: (deviceId: string, limit?: number) =>
    api.get(`/snmp/history/${deviceId}`, { params: { limit } }),
}

// === Agents ===
export const agentsApi = {
  list: (params?: Record<string, unknown>) => api.get('/agents', { params }),
  register: (data: Record<string, unknown>) => api.post('/agents/register', data),
  deactivate: (id: string) => api.delete(`/agents/${id}`),
  details: (id: string, hours = 24) => api.get(`/agents/${id}/details`, { params: { hours } }),
}

// === Dashboard ===
export const dashboardApi = {
  overview: () => api.get('/dashboard/overview'),
}

export default api
