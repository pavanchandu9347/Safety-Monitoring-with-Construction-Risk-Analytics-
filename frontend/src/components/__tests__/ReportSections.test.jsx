import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportSections } from '../ReportSections.jsx'

// Regression: the structured report renderer used to crash with
// "ReferenceError: ListChecks is not defined" when a report with compliance
// sections / prioritized actions was rendered (the black-screen bug).
const report = {
  id: 'rpt_001',
  title: 'Risk Intelligence Report',
  content: {
    site_info: { site_name: 'Riverside Tower', site_id: 'site_riverside_main' },
    analysis_info: { video_source: 'Contruction_vid.mp4', frames_analyzed: 20 },
    executive_summary: { risk_trend_direction: 'STABLE', short_line: 'Stable risk posture after controls.', key_concerns: ['Exposed rebar'] },
    sections: {
      risk: {
        status: 'available',
        overall_score: 42,
        risk_level: 'MEDIUM',
        site_risk: { hazards_by_severity: { HIGH: 1 } },
        components: [{ label: 'ENVIRONMENTAL', score: 30 }],
      },
      safety: { status: 'NOT_AVAILABLE' },
      compliance: {
        status: 'available',
        compliance_level: 'PARTIAL',
        overall_score: 45,
        compliant_count: 3,
        non_compliant_count: 1,
        not_verified_count: 2,
        requirements_checked: 4,
      },
      insurance: { status: 'NOT_AVAILABLE' },
    },
    critical_findings: [],
    high_findings: [
      { title: 'Missing fall protection near the eastern edge', hazard_type: 'FALL', severity: 'HIGH' },
    ],
    prioritized_actions: [
      { title: 'Install guardrails on level 3 edge', priority: 'HIGH', description: 'Fit temporary edge protection', source: 'RiskAgent' },
    ],
    evidence_summary: {
      data_quality: { label: 'ADEQUATE' },
      counts: { compliance_findings: 1 },
    },
    historical_analytics: { series: [] },
  },
}

describe('ReportSections', () => {
  it('renders the executive summary section', () => {
    render(<ReportSections report={report} history={null} />)
    expect(screen.getByText('EXECUTIVE RISK SUMMARY')).toBeInTheDocument()
    expect(screen.getByText('Riverside Tower')).toBeInTheDocument()
  })

  it('renders risk analytics with the overall score and level', () => {
    render(<ReportSections report={report} history={null} />)
    expect(screen.getByText('RISK ANALYTICS')).toBeInTheDocument()
    expect(screen.getByText(/LEVEL MEDIUM/i)).toBeInTheDocument()
  })

  it('renders compliance sections (ListChecks icon path) without crashing', async () => {
    const user = userEvent.setup()
    render(<ReportSections report={report} history={null} />)
    await user.click(screen.getByText('COMPLIANCE INTELLIGENCE'))
    expect(screen.getByText('CHECKED')).toBeInTheDocument()
  })

  it('renders prioritized actions and critical findings', async () => {
    const user = userEvent.setup()
    render(<ReportSections report={report} history={null} />)
    expect(screen.getByText(/Missing fall protection/i)).toBeInTheDocument()
    await user.click(screen.getByText('RECOMMENDATIONS'))
    expect(screen.getByText(/Install guardrails/i)).toBeInTheDocument()
  })
})