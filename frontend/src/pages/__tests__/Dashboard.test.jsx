import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Dashboard from '../Dashboard.jsx'
import { AuthProvider } from '../../contexts/AuthContext'

vi.mock('../../services/api', () => ({
  api: {
    getDashboard: vi.fn(),
    getLiveStatus: vi.fn(),
    listVideoSources: vi.fn(),
    getLatestVideoAnalysis: vi.fn(),
    getSafetyDashboard: vi.fn(),
    getComplianceDashboard: vi.fn(),
    getInsuranceDashboard: vi.fn(),
    getNotifications: vi.fn(),
    analyzeVideo: vi.fn(),
    generateDemo: vi.fn(),
    liveVideoUrl: () => '/api/sites/site_riverside_main/live/video',
    liveWsUrl: () => 'ws://localhost/api/ws/sites/site_riverside_main/live',
  },
}))

const { api } = await import('../../services/api')

const dashboardData = {
  site_id: 'site_riverside_main',
  current_risk_assessment: {
    overall_score: 42,
    risk_level: 'MEDIUM',
    summary: 'Medium risk from exposed rebar and active crane work.',
  },
  zone_risk_data: [],
  active_hazards: [],
  critical_hazards: [],
  open_hazards: 0,
  active_hazards_count: 0,
  total_recommendations: 0,
  equipment: [],
  risk_trend: [],
}

const renderDashboard = () =>
  render(
    <BrowserRouter>
      <AuthProvider>
        <Dashboard />
      </AuthProvider>
    </BrowserRouter>
  )

describe('Dashboard page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    api.getDashboard.mockResolvedValue({ data: dashboardData })
    api.getLiveStatus.mockResolvedValue({ data: { status: 'STOPPED' } })
    api.listVideoSources.mockResolvedValue({ data: { default: null, videos: [] } })
    api.getLatestVideoAnalysis.mockResolvedValue({ data: { status: 'none' } })
    api.getNotifications.mockResolvedValue({ data: [] })
  })

  it('renders the operations center with real risk data once loaded', async () => {
    renderDashboard()
    expect(await screen.findByText('RIVERSIDE TOWER — SITE A1')).toBeInTheDocument()
    expect(screen.getAllByText('MEDIUM').length).toBeGreaterThan(0)
  })

  it('shows the SYS OFFLINE state when the dashboard API fails', async () => {
    api.getDashboard.mockRejectedValue(new Error('backend unreachable'))
    renderDashboard()
    expect(await screen.findByText(/SYS OFFLINE/i)).toBeInTheDocument()
  })
})