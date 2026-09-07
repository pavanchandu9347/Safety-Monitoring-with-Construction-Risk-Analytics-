import axios from 'axios'

const API = axios.create({
  baseURL: '/api',
})

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

  // ── Live video-analysis pipeline ────────────────────────────────────
  getLiveStatus: (siteId) => API.get(`/sites/${siteId}/live/status`),
  startLive: (siteId, body = {}) => API.post(`/sites/${siteId}/live/start`, body),
  stopLive: (siteId) => API.post(`/sites/${siteId}/live/stop`),
  liveVideoUrl: (siteId) => `/api/sites/${siteId}/live/video`,
  liveWsUrl: (siteId) => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/api/ws/sites/${siteId}/live`
  },
}

export default API
