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
    formData.append('site_id', siteId)
    return API.post('/monitoring/process-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
  },
  getDemoScenario: () => API.get('/demo/scenario'),
  getEnvironmentalDemo: (zoneType) => API.get('/demo/environmental', { params: { zone_type: zoneType } }),
  getEquipmentDemo: () => API.get('/demo/equipment'),
}

export default API
