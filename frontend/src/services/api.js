import axios from 'axios'

const API = axios.create({
  baseURL: '/api',
})

// Attach the JWT to every request (Bearer header). Stream endpoints that
// cannot send headers (MJPEG <img>) read the same token from the query string.
API.interceptors.request.use((config) => {
  const token = localStorage.getItem('buildsure_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// A 401 means the token is missing/expired/revoked: clear session state and
// send the operator back to the login screen.
API.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401 && !err.config?.url?.startsWith('/auth/login')) {
      localStorage.removeItem('buildsure_token')
      localStorage.removeItem('buildsure_manager')
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(err)
  }
)

export const api = {
  getDashboard: (siteId) => API.get(`/sites/${siteId}/dashboard`),
  getSites: () => API.get('/sites'),
  getZones: (siteId) => API.get(`/sites/${siteId}/zones`),
  getHazards: (siteId, params = {}) => API.get(`/sites/${siteId}/hazards`, { params }),
  getHazard: (hazardId) => API.get(`/hazards/${hazardId}`),
  updateHazardStatus: (hazardId, newStatus) =>
    API.patch(`/hazards/${hazardId}/status`, null, { params: { new_status: newStatus } }),
  getCurrentRisk: (siteId) => API.get(`/sites/${siteId}/risk`),
  getRiskHistory: (siteId) => API.get(`/sites/${siteId}/risk/history`),
  getRiskAnalysis: (siteId) => API.post(`/sites/${siteId}/risk/analyze`),
  getRecommendations: (siteId) => API.get(`/sites/${siteId}/recommendations`),
  getMonitoring: (siteId) => API.get(`/sites/${siteId}/monitoring`),
  simulateMonitoring: (siteId) => API.post(`/monitoring/simulate`, null, { params: { site_id: siteId } }),
  generateDemo: (siteId) => API.post(`/demo/generate`, null, { params: { site_id: siteId } }),
  processImage: (siteId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    // Let the browser set Content-Type with the multipart boundary; some other
    // http clients (axios XHR) would otherwise send an invalid no-boundary
    // multipart body that FastAPI/python-multipart cannot parse.
    return API.post('/monitoring/process-image', formData, {
      params: { site_id: siteId },
      timeout: 120000,
    })
  },
  getDemoScenario: () => API.get('/demo/scenario'),
  getEnvironmentalDemo: (zoneType) => API.get('/demo/environmental', { params: { zone_type: zoneType } }),
  getEquipmentDemo: () => API.get('/demo/equipment'),
  getSafetyDashboard: (siteId) => API.get(`/sites/${siteId}/safety/dashboard`),
  getSafetyAnalysis: (siteId) => API.post(`/sites/${siteId}/safety/analyze`),
  getWorkers: (siteId) => API.get(`/sites/${siteId}/workers`),
  getSafetyViolations: (siteId, params = {}) => API.get(`/sites/${siteId}/safety/violations`, { params }),
  getSafetyAlerts: (siteId) => API.get(`/sites/${siteId}/safety/alerts`),
  updateViolationStatus: (violationId, status) =>
    API.patch(`/safety/violations/${violationId}/status`, null, { params: { status } }),

  // ── Unified video-analysis pipeline (single primary input) ──────────
  listVideoSources: (siteId) => API.get('/video/source', { params: { site_id: siteId } }),
  analyzeVideo: (siteId, { videoPath = '', file = null, conf = 0 } = {}) => {
    if (file) {
      const formData = new FormData()
      formData.append('site_id', siteId)
      formData.append('file', file)
      if (conf > 0) formData.append('conf', String(conf))
      return API.post('/video/analyze', formData, { timeout: 300000 })
    }
    return API.post('/video/analyze', null, {
      params: { site_id: siteId, video_path: videoPath, conf },
      timeout: 300000,
    })
  },
  getVideoAnalysis: (analysisId) => API.get(`/video/analysis/${analysisId}`),
  getLatestVideoAnalysis: (siteId) => API.get(`/sites/${siteId}/video/analysis/latest`),
  listSiteAnalyses: (siteId) => API.get(`/sites/${siteId}/video/analysis`),
  getLatestRiskAnalysis: (siteId) => API.get(`/sites/${siteId}/risk/latest`),

  // ── Compliance Intelligence (M3) ──────────────────────────────────────
  runComplianceAnalysis: (siteId) => API.post(`/sites/${siteId}/compliance/analyze`, {}, { timeout: 300000 }),
  getComplianceDashboard: (siteId) => API.get(`/sites/${siteId}/compliance/dashboard`),
  getComplianceFindings: (siteId) => API.get(`/sites/${siteId}/compliance/findings`),
  getComplianceRequirements: (siteId) => API.get(`/sites/${siteId}/compliance/requirements`),
  getComplianceInspections: (siteId) => API.get(`/sites/${siteId}/compliance/inspections`),
  getComplianceAssessment: (siteId) => API.get(`/sites/${siteId}/compliance/assessment`),

  // ── Insurance Intelligence (M3) ──────────────────────────────────────
  runInsuranceAnalysis: (siteId) => API.post(`/sites/${siteId}/insurance/analyze`, {}, { timeout: 300000 }),
  getInsuranceDashboard: (siteId) => API.get(`/sites/${siteId}/insurance/dashboard`),
  getInsuranceIncidents: (siteId) => API.get(`/sites/${siteId}/insurance/incidents`),
  getInsuranceClaims: (siteId) => API.get(`/sites/${siteId}/insurance/claims`),
  getInsuranceAssessment: (siteId) => API.get(`/sites/${siteId}/insurance/assessment`),

  // ── Live video-analysis pipeline ────────────────────────────────────
  getLiveStatus: (siteId) => API.get(`/sites/${siteId}/live/status`),
  startLive: (siteId, body = {}) => API.post(`/sites/${siteId}/live/start`, body),
  stopLive: (siteId) => API.post(`/sites/${siteId}/live/stop`),
  liveVideoUrl: (siteId) => {
    const token = localStorage.getItem('buildsure_token') || ''
    const q = token ? `?token=${encodeURIComponent(token)}` : ''
    return `/api/sites/${siteId}/live/video${q}`
  },
  liveWsUrl: (siteId) => {
    const token = localStorage.getItem('buildsure_token') || ''
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/api/ws/sites/${siteId}/live?token=${encodeURIComponent(token)}`
  },

  // ── Manager authentication (M4) ──────────────────────────────────────
  login: (email, password) => API.post('/auth/login', { email, password }),
  getMe: () => API.get('/auth/me'),
  logout: () => API.post('/auth/logout'),

  // ── Evidence-based risk alerts / notifications (M4) ──────────────────
  getNotifications: (params = {}) => API.get('/notifications', { params }),
  getUnreadCount: () => API.get('/notifications/unread-count'),
  markNotificationRead: (id) => API.patch(`/notifications/${id}/read`),
  markAllNotificationsRead: (siteId) =>
    API.patch('/notifications/read-all', null, { params: siteId ? { site_id: siteId } : {} }),
  deleteNotification: (id) => API.delete(`/notifications/${id}`),
}

export default API
