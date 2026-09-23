import axios from 'axios'

// VITE_API_URL defaults to the same-origin /api path (nginx proxies it to the
// backend). Set it to an absolute URL only when the API lives on another origin
// (the backend's CORS_ALLOW_ORIGINS must include the app origin then).
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
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

// Analyses run asynchronously (status: queued → processing → completed|failed).
// Submit, then poll the analysis record until it reaches a terminal state so
// callers keep the same await-and-use contract they had with the synchronous
// pipeline.
async function waitForAnalysis(analysisId, { timeoutMs = 20 * 60 * 1000, intervalMs = 2500 } = {}) {
  const deadline = Date.now() + timeoutMs
  let last = null
  while (Date.now() < deadline) {
    const { data } = await API.get(`/video/analysis/${analysisId}`)
    last = data
    if (data.status === 'completed') return data
    if (data.status === 'failed') {
      const err = new Error(data.error || 'Video analysis failed.')
      err.response = { data: { detail: data.error || 'Video analysis failed.' } }
      throw err
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  const err = new Error(last?.status ? `Analysis still ${last.status} after the timeout.` : 'Analysis timed out.')
  err.response = { data: { detail: err.message } }
  throw err
}

// Resolve the running API origin + WebSocket scheme from the configured base
// (same-origin /api or an absolute VITE_API_URL). Works behind nginx and under
// TLS (wss://) automatically.
function apiOrigin() {
  const base = import.meta.env.VITE_API_URL || '/api'
  if (base.startsWith('/')) return window.location.origin + base
  return base.replace(/\/$/, '')
}
function wsBase() {
  const base = apiOrigin()
  const ws = base.replace(/^http/, 'ws')
  return ws.endsWith('/') ? ws.slice(0, -1) : ws
}

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
  generateDemo: async (siteId) => {
    const { data } = await API.post('/demo/generate', null, { params: { site_id: siteId } })
    if (data.status === 'queued' && data.analysis_id) return waitForAnalysis(data.analysis_id)
    return data
  },
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
  analyzeVideo: async (siteId, { videoPath = '', file = null, conf = 0 } = {}) => {
    let data
    if (file) {
      const formData = new FormData()
      formData.append('site_id', siteId)
      formData.append('file', file)
      if (conf > 0) formData.append('conf', String(conf))
      ;({ data } = await API.post('/video/analyze', formData, { timeout: 600000 }))
    } else {
      ;({ data } = await API.post('/video/analyze', null, {
        params: { site_id: siteId, video_path: videoPath, conf },
        timeout: 600000,
      }))
    }
    if (data.status === 'queued' && data.analysis_id) return waitForAnalysis(data.analysis_id)
    return data
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
    return `${apiOrigin()}/sites/${siteId}/live/video${q}`
  },
  liveWsUrl: (siteId) => {
    const token = localStorage.getItem('buildsure_token') || ''
    return `${wsBase()}/ws/sites/${siteId}/live?token=${encodeURIComponent(token)}`
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

  // ── Reporting Intelligence & Enterprise Deployment (M4) ─────────────
  getIntelligence: (siteId, analysisId = null) =>
    API.get(`/sites/${siteId}/intelligence`, { params: analysisId ? { analysis_id: analysisId } : {} }),
  getAnalyticsHistory: (siteId) => API.get(`/sites/${siteId}/analytics/history`),
  generateReport: (siteId, { analysisId = null, reportType = 'risk_intelligence' } = {}) =>
    API.post(
      `/sites/${siteId}/reports/generate`,
      { analysis_id: analysisId, report_type: reportType },
      { timeout: 300000 }
    ),
  getReports: (siteId) => API.get(`/sites/${siteId}/reports`),
  getLatestReport: (siteId) => API.get(`/sites/${siteId}/reports/latest`),
  getReport: (siteId, reportId) => API.get(`/sites/${siteId}/reports/${reportId}`),
  getReportText: (siteId, reportId) => API.get(`/sites/${siteId}/reports/${reportId}/text`),
  getReportPdf: (siteId, reportId) =>
    API.get(`/sites/${siteId}/reports/${reportId}/pdf`, { responseType: 'blob' }),
}

export default API
