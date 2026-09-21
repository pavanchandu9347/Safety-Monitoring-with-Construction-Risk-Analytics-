import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { StatChip, Section, ActionBar } from '../components/progressive'
import {
  ShieldAlert, AlertTriangle, FileText, Activity, Gauge, Users, Flame,
  RefreshCw, Info,
} from 'lucide-react'

const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const LEVEL_BG = {
  LOW: 'rgba(54,209,126,0.12)', MEDIUM: 'rgba(245,166,35,0.12)',
  HIGH: 'rgba(255,122,60,0.14)', CRITICAL: 'rgba(255,90,60,0.16)',
}

function ScoreRing({ score, level }) {
  const color = LEVEL_HEX[level] || '#36d17e'
  const R = 44, C = 2 * Math.PI * R
  const filled = (score / 100) * C
  return (
    <div className="relative w-[120px] h-[120px] mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={R} fill="none" stroke="#1c2530" strokeWidth="6" />
        <circle cx="60" cy="60" r={R} fill="none" stroke={color} strokeWidth="6"
          strokeLinecap="round" strokeDasharray={`${filled} ${C}`}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="readout text-[28px] font-black text-white tabular-nums">{Math.round(score)}</div>
        <div className="readout text-[9px] font-bold tracking-[0.15em] mt-0.5" style={{ color }}>{level}</div>
        <div className="text-[8px] text-slate-500 readout tracking-widest mt-0.5">RISK SCORE</div>
      </div>
    </div>
  )
}

const TABS = [
  { key: 'incidents', label: 'Incidents', icon: AlertTriangle },
  { key: 'exposure', label: 'Exposure', icon: Gauge },
  { key: 'claims', label: 'Claims', icon: FileText },
  { key: 'recommendations', label: 'Recommendations', icon: Info },
]

const EXPOSURE_DIMS = [
  { key: 'worker_safety', label: 'Workers', icon: Users },
  { key: 'equipment', label: 'Equipment', icon: Activity },
  { key: 'ppe', label: 'PPE', icon: ShieldAlert },
  { key: 'incident', label: 'Incidents', icon: Flame },
]

export default function Insurance() {
  const siteId = useSite()
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [tab, setTab] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.getInsuranceDashboard(siteId)
      setDash(res.data)
      setError(null)
    } catch {
      setDash(null)
      setError('No insurance data available — run a video analysis first.')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.runInsuranceAnalysis(siteId); await load() } finally { setRunning(false) }
  }

  if (loading) return (
    <div className="p-6 flex items-center gap-3 text-slate-400 readout text-sm">
      <RefreshCw size={14} className="animate-spin text-info" /> Loading insurance data…
    </div>
  )

  if (error && !dash) return (
    <div className="p-6">
      <div className="tech-panel p-5 border-l-signal">
        <p className="readout text-signal font-bold">⚠ {error}</p>
        <p className="readout text-slate-400 text-xs mt-2">Click "Run Analysis" to generate insurance risk intelligence from the current video.</p>
        <button onClick={runAnalysis} disabled={running}
          className="mt-3 flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          <RefreshCw size={13} className={running ? 'animate-spin' : ''} /> {running ? 'RUNNING...' : 'RUN ANALYSIS'}
        </button>
      </div>
    </div>
  )

  const assess   = dash?.current_assessment
  const score    = assess?.risk_score ?? 0
  const level    = assess?.risk_level ?? 'LOW'
  const incidents = dash?.incidents || []
  const exposure = assess?.exposure?.overall || {}
  const claimRisk = assess?.claim_risk || {}
  const docs     = dash?.claim_documentation?.documents || (dash?.claim_records || [])
  const docCount = dash?.claim_documentation?.count ?? dash?.open_claims ?? docs.length
  const recs     = dash?.recommendations || []

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="text-hazard" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">INSURANCE INTELLIGENCE</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">
            RISK EXPOSURE · INCIDENT SEVERITY · CLAIM ASSESSMENT
          </div>
        </div>
        <button onClick={runAnalysis} disabled={running}
          className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          <RefreshCw size={13} className={running ? 'animate-spin' : ''} /> {running ? 'RUNNING...' : 'RUN ANALYSIS'}
        </button>
      </div>
      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      {/* Overview grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-1 tech-panel p-4 flex flex-col items-center justify-center">
          <div className="bracket-label self-start mb-2 flex items-center gap-1.5"><ShieldAlert size={12} /> OVERALL RISK</div>
          <ScoreRing score={score} level={level} />
          <p className="readout text-[10px] text-slate-500 mt-3 text-center">
            {incidents.length} incident(s) · {docCount} claim document(s) · claim risk {claimRisk.claim_risk_level || '—'}
          </p>
        </div>

        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatChip icon={Gauge} label="Risk Score" value={`${score.toFixed(0)}`} accent={LEVEL_HEX[level]} sub={level} />
          <StatChip icon={AlertTriangle} label="Incidents" value={incidents.length} accent={incidents.length > 0 ? '#ff7a3c' : '#36d17e'} sub={`${dash?.open_incidents ?? 0} open`} />
          <StatChip icon={FileText} label="Claim Docs" value={docCount} accent={docCount > 0 ? '#f5a623' : '#36d17e'} sub={dash?.claim_documentation?.status || '—'} />
          <StatChip icon={Gauge} label="Overall Exposure" value={exposure.level?.toUpperCase() || '—'} accent={LEVEL_HEX[exposure.level] || '#94a3b8'} sub={`${exposure.score ?? 0} / 100`} />
        </div>
      </div>

      {/* Exposure bars */}
      <div className="tech-panel p-4">
        <div className="bracket-label mb-3 flex items-center gap-1.5"><Gauge size={12} /> EXPOSURE BREAKDOWN</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-[#0a0e13] border border-steel p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="readout text-[10px] text-slate-400 tracking-wider">OVERALL</span>
              <span className="readout text-[10px] font-bold" style={{ color: LEVEL_HEX[exposure.level] || '#94a3b8' }}>
                {exposure.level?.toUpperCase() || '—'} · {exposure.score ?? 0}
              </span>
            </div>
            <div className="h-1.5 bg-[#1a1f27] border border-steel/50 rounded-full overflow-hidden">
              <div className="h-full" style={{
                width: `${exposure.score ?? 0}%`,
                background: LEVEL_HEX[exposure.level] || '#94a3b8',
                boxShadow: `0 0 6px ${LEVEL_HEX[exposure.level] || '#94a3b8'}`,
              }} />
            </div>
          </div>
          {EXPOSURE_DIMS.map(({ key, label, icon: Icon }) => {
            const dim = assess?.exposure?.[key] || {}
            const c = LEVEL_HEX[dim.level] || '#94a3b8'
            return (
              <div key={key} className="bg-[#0a0e13] border border-steel p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="readout text-[10px] text-slate-400 tracking-wider flex items-center gap-1"><Icon size={11} /> {label.toUpperCase()}</span>
                  <span className="readout text-[10px] font-bold" style={{ color: c }}>{dim.level?.toUpperCase() || '—'}</span>
                </div>
                <div className="h-1.5 bg-[#1a1f27] border border-steel/50 rounded-full overflow-hidden">
                  <div className="h-full" style={{
                    width: `${dim.score ?? 0}%`,
                    background: c, boxShadow: `0 0 6px ${c}`,
                  }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Tabs */}
      <ActionBar items={TABS} active={tab} onToggle={(k) => setTab(tab === k ? null : k)} />

      {/* Incidents tab */}
      {tab === 'incidents' && (
        <Section title="SAFETY INCIDENTS" badge={incidents.length} onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {incidents.map((inc) => {
              const c = LEVEL_HEX[inc.severity] || '#94a3b8'
              const involved = Array.isArray(inc.workers_involved)
                ? inc.workers_involved.reduce((s, w) => s + (w.count || 0), 0) : 0
              return (
                <div key={inc.id} className="bg-[#0a0e13] border border-steel p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="readout text-[11px] text-slate-200 font-semibold">{inc.incident_type?.toUpperCase()}</span>
                    <span className="readout text-[9px] font-bold px-1.5 py-0.5"
                      style={{ color: c, border: `1px solid ${c}`, background: LEVEL_BG[inc.severity] || 'transparent' }}>
                      {inc.severity}
                    </span>
                  </div>
                  <p className="readout text-[10px] text-slate-400 leading-relaxed">{inc.description}</p>
                  <div className="readout text-[9px] text-slate-600 mt-1 tracking-wider">
                    {involved > 0 && `WORKERS: ${involved} · `}{formatTime(inc.timestamp)} · {inc.hazards?.length || 0} hazard ref(s)
                  </div>
                </div>
              )
            })}
            {incidents.length === 0 && <div className="readout text-[11px] text-slate-500">NO INCIDENTS — RUN ANALYSIS</div>}
          </div>
        </Section>
      )}

      {/* Exposure tab */}
      {tab === 'exposure' && (
        <Section title="EXPOSURE DETAILS" onClose={() => setTab(null)}>
          <div className="space-y-3">
            <div className="bg-[#0a0e13] border border-steel p-3">
              <div className="bracket-label mb-2">EXPOSURE DIMENSIONS</div>
              <div className="space-y-1">
                {[{ label: 'Overall', dim: exposure }, ...EXPOSURE_DIMS.map(({ key, label }) => ({ label, dim: assess?.exposure?.[key] || {} }))].map(({ label, dim }) => {
                  const c = LEVEL_HEX[dim.level] || '#94a3b8'
                  return (
                    <div key={label} className="flex items-center justify-between py-1 border-b border-steel/30 last:border-0">
                      <span className="readout text-[10px] text-slate-400 tracking-wider">{label.toUpperCase()}</span>
                      <span className="readout text-[11px] font-bold" style={{ color: c }}>
                        {dim.level?.toUpperCase() || '—'} · {dim.score ?? 0}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {[{ label: 'Workers', dim: assess?.exposure?.worker_safety }, { label: 'Equipment', dim: assess?.exposure?.equipment }].map(({ label, dim }) => (
                <div key={label} className="bg-[#0a0e13] border border-steel p-3">
                  <div className="bracket-label mb-2">{label.toUpperCase()} RISK FACTORS</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(dim?.factors || []).map((f, i) => (
                      <span key={i} className="readout text-[9px] text-slate-300 px-1.5 py-0.5 border border-slate-600 tracking-wider">{f}</span>
                    ))}
                    {(dim?.factors || []).length === 0 && <span className="readout text-[9px] text-slate-600">NO FACTORS</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className="bg-[#0a0e13] border border-steel p-3">
              <div className="bracket-label mb-2">CLAIM RISK ASSESSMENT</div>
              <div className="flex items-center justify-between py-1 border-b border-steel/30">
                <span className="readout text-[10px] text-slate-400 tracking-wider">CLAIM RISK</span>
                <span className="readout text-[11px] font-bold" style={{ color: LEVEL_HEX[claimRisk.claim_risk_level] || '#94a3b8' }}>
                  {claimRisk.claim_risk_level || '—'} · {claimRisk.claim_risk_score ?? 0}
                </span>
              </div>
              {(claimRisk.contributing_factors || []).map((f, i) => (
                <div key={i} className="readout text-[9px] text-slate-500 mt-1 tracking-wider">▸ {f}</div>
              ))}
            </div>
          </div>
        </Section>
      )}

      {/* Claims tab */}
      {tab === 'claims' && (
        <Section title="CLAIM DOCUMENTATION" badge={docCount} onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {docs.map((doc, i) => (
              <div key={doc.document_id || i} className="bg-[#0a0e13] border border-steel p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="readout text-[11px] text-slate-200 font-semibold">
                    {doc.incident_type?.toUpperCase()} {doc.document_id && <span className="text-slate-500 font-normal">· {doc.document_id}</span>}
                  </span>
                  <span className="readout text-[9px] px-1.5 py-0.5"
                    style={{ color: LEVEL_HEX[doc.severity] || '#f5a623', border: `1px solid ${LEVEL_HEX[doc.severity] || '#f5a623'}` }}>
                    {doc.severity || doc.status || '—'}
                  </span>
                </div>
                <p className="readout text-[10px] text-slate-400 leading-relaxed">{doc.description || doc.claim_summary}</p>
                <div className="readout text-[9px] text-slate-600 mt-1 tracking-wider">
                  {doc.workers_involved && `WORKERS: ${doc.workers_involved} · `}{doc.incident_date && formatTime(doc.incident_date)} {doc.location ? `· LOCATION: ${doc.location}` : ''}
                </div>
              </div>
            ))}
            {docs.length === 0 && <div className="readout text-[11px] text-slate-500">NO CLAIM DOCUMENTS</div>}
          </div>
        </Section>
      )}

      {/* Recommendations tab */}
      {tab === 'recommendations' && (
        <Section title="RECOMMENDATIONS" onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {recs.map((r, i) => (
              <div key={i} className="bg-[#0a0e13] border border-steel p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="readout text-[11px] text-slate-200 font-semibold">{r.category?.toUpperCase()}</span>
                  <span className="readout text-[9px] px-1.5 py-0.5 font-bold"
                    style={{ color: r.priority === 'HIGH' ? '#ff7a3c' : r.priority === 'CRITICAL' ? '#ff5a3c' : '#36d17e',
                      border: `1px solid ${r.priority === 'HIGH' ? '#ff7a3c' : r.priority === 'CRITICAL' ? '#ff5a3c' : '#36d17e'}` }}>
                    {r.priority}
                  </span>
                </div>
                <p className="readout text-[10px] text-slate-400 leading-relaxed">{r.recommendation || r.description}</p>
                {(r.evidence || []).slice(0, 3).map((e, j) => (
                  <div key={j} className="readout text-[9px] text-slate-600 mt-0.5 tracking-wider">▸ {e}</div>
                ))}
              </div>
            ))}
            {recs.length === 0 && <div className="readout text-[11px] text-slate-500">NO RECOMMENDATIONS</div>}
          </div>
        </Section>
      )}
    </div>
  )
}