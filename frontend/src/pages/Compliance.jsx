import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { StatChip, Section, ActionBar } from '../components/progressive'
import {
  ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, Clock,
  ListChecks, FileWarning, RefreshCw, Info,
} from 'lucide-react'

const LEVEL_HEX = {
  COMPLIANT: '#36d17e', PARTIAL: '#f5a623', NON_COMPLIANT: '#ff5a3c',
  NOT_VERIFIED: '#94a3b8', INSUFFICIENT_EVIDENCE: '#94a3b8',
}

function ScoreRing({ score, status }) {
  const color = LEVEL_HEX[status] || '#94a3b8'
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
        <div className="readout text-[9px] font-bold tracking-[0.15em] mt-0.5" style={{ color }}>{status?.replace(/_/g, ' ')}</div>
      </div>
    </div>
  )
}

const TABS = [
  { key: 'findings', label: 'Findings', icon: FileWarning },
  { key: 'requirements', label: 'Requirements', icon: ListChecks },
  { key: 'inspections', label: 'Inspections', icon: Clock },
  { key: 'violations', label: 'Open Violations', icon: ShieldAlert },
  { key: 'recommendations', label: 'Recommendations', icon: Info },
]

function RequirementBadge({ status }) {
  if (status === 'COMPLIANT') {
    return (
      <span className="readout text-[9px] font-bold px-1.5 py-0.5 shrink-0"
        style={{ color: '#36d17e', border: '1px solid #36d17e' }}>MET</span>
    )
  }
  if (status === 'NOT_VERIFIED' || status === 'INSUFFICIENT_EVIDENCE') {
    return (
      <span className="readout text-[9px] font-bold px-1.5 py-0.5 shrink-0"
        style={{ color: '#94a3b8', border: '1px solid #475569' }}>NOT VERIFIED</span>
    )
  }
  return (
    <span className="readout text-[9px] font-bold px-1.5 py-0.5 shrink-0"
      style={{ color: '#ff5a3c', border: '1px solid #ff5a3c' }}>NOT MET</span>
  )
}

export default function Compliance() {
  const siteId = useSite()
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [tab, setTab] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.getComplianceDashboard(siteId)
      setDash(res.data)
      setError(null)
    } catch {
      setDash(null)
      setError('No compliance data available — run a video analysis first.')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.runComplianceAnalysis(siteId); await load() } finally { setRunning(false) }
  }

  if (loading) return (
    <div className="p-6 flex items-center gap-3 text-slate-400 readout text-sm">
      <RefreshCw size={14} className="animate-spin text-info" /> Loading compliance data…
    </div>
  )

  if (error && !dash) return (
    <div className="p-6">
      <div className="tech-panel p-5 border-l-signal">
        <p className="readout text-signal font-bold">⚠ {error}</p>
        <p className="readout text-slate-400 text-xs mt-2">Click "Run Analysis" to generate compliance intelligence from the current video.</p>
        <button onClick={runAnalysis} disabled={running}
          className="mt-3 flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          <RefreshCw size={13} className={running ? 'animate-spin' : ''} /> {running ? 'RUNNING...' : 'RUN ANALYSIS'}
        </button>
      </div>
    </div>
  )

  const assess   = dash?.current_assessment
  const score    = assess?.overall_score ?? 0
  const status   = assess?.compliance_level ?? 'NOT_VERIFIED'
  const findings = dash?.findings || []
  const overdue  = dash?.overdue_inspections ?? 0
  const openV    = assess?.open_violations ?? 0
  const reqs     = assess?.compliant_count ?? 0
  const totalReq = dash?.total_requirements ?? 0
  const checked  = assess?.requirements_checked ?? 0
  const unavail  = dash?.unavailable_evidence || []
  const recs     = dash?.recommendations || []

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="text-hazard" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">COMPLIANCE INTELLIGENCE</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">
            REGULATORY STANDARDS · INSPECTION STATUS · EVIDENCE VERIFICATION
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
          <div className="bracket-label self-start mb-2 flex items-center gap-1.5"><ShieldCheck size={12} /> OVERALL COMPLIANCE</div>
          <ScoreRing score={score} status={status} />
          <p className="readout text-[10px] text-slate-500 mt-3 text-center">
            {reqs}/{checked} of {totalReq} requirements verified compliant · {findings.length} findings
          </p>
        </div>

        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatChip icon={CheckCircle2} label="Compliant" value={`${score.toFixed(0)}%`} accent="#36d17e" sub={`${reqs}/${totalReq} requirements`} />
          <StatChip icon={FileWarning} label="Findings" value={findings.length} accent="#f5a623" sub={`${checked} verified`} />
          <StatChip icon={Clock} label="Inspections" value={overdue > 0 ? `${overdue} overdue` : 'CLEAR'} accent={overdue > 0 ? '#ff7a3c' : '#36d17e'} sub={overdue > 0 ? 'Action required' : 'All up to date'} />
          <StatChip icon={AlertTriangle} label="Open Violations" value={openV} accent={openV > 0 ? '#ff5a3c' : '#36d17e'} />
        </div>
      </div>

      {/* Unavailable evidence banner */}
      {unavail.length > 0 && (
        <div className="tech-panel p-4 border-l-[2px] border-[#94a3b8] bg-[#94a3b8]/5">
          <p className="readout text-[11px] text-[#94a3b8] font-bold flex items-center gap-1.5">
            <Info size={13} /> INSUFFICIENT EVIDENCE — {unavail.length} item(s)
          </p>
          <p className="readout text-[10px] text-slate-400 mt-1">
            Documentation or visual evidence was unavailable. Status set to <span className="text-white font-semibold">NOT_VERIFIED</span> — no data was fabricated.
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">
            {unavail.slice(0, 8).map((item, i) => (
              <span key={i} className="readout text-[9px] text-slate-400 px-1.5 py-0.5 border border-[#475569] tracking-wider" title={item.reason}>
                {item.category.toUpperCase()}
              </span>
            ))}
            {unavail.length > 8 && <span className="readout text-[9px] text-slate-500">+{unavail.length - 8} more</span>}
          </div>
        </div>
      )}

      {/* Tabs */}
      <ActionBar items={TABS} active={tab} onToggle={(k) => setTab(tab === k ? null : k)} />

      {/* Findings tab */}
      {tab === 'findings' && (
        <Section title="COMPLIANCE FINDINGS" badge={findings.length} onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {findings.map((f) => {
              const c = LEVEL_HEX[f.status] || '#94a3b8'
              return (
                <div key={f.id} className="bg-[#0a0e13] border border-steel p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="readout text-[11px] text-slate-200 font-semibold">{f.requirement}</span>
                    <span className="readout text-[9px] font-bold px-1.5 py-0.5"
                      style={{ color: c, border: `1px solid ${c}` }}>{f.status}</span>
                  </div>
                  <p className="readout text-[10px] text-slate-400 leading-relaxed">{f.description}</p>
                  <div className="readout text-[9px] text-slate-500 mt-1 tracking-wider">
                    CATEGORY: {f.category?.toUpperCase()} · SOURCE: {f.source?.replace(/_/g, ' ').toUpperCase()} · {formatTime(f.timestamp)}
                  </div>
                  {f.status === 'NOT_VERIFIED' && (
                    <div className="readout text-[9px] text-slate-500 mt-0.5">REASON: {f.evidence || 'No evidence available'}</div>
                  )}
                </div>
              )
            })}
            {findings.length === 0 && <div className="readout text-[11px] text-slate-500">NO FINDINGS — RUN ANALYSIS</div>}
          </div>
        </Section>
      )}

      {/* Requirements tab */}
      {tab === 'requirements' && (
        <Section title="COMPLIANCE REQUIREMENTS" onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {findings.map((f) => (
              <div key={f.id} className="flex items-start justify-between gap-3 bg-[#0a0e13] border border-steel p-3">
                <div className="min-w-0">
                  <div className="readout text-[11px] text-slate-200 font-semibold">{f.requirement}</div>
                  <div className="readout text-[9px] text-slate-500 mt-0.5">CATEGORY: {f.category?.toUpperCase()} · {f.status}</div>
                  {f.status === 'NOT_VERIFIED' && (
                    <div className="readout text-[9px] text-slate-500 mt-0.5">{f.evidence || 'No evidence available — not counted as non-compliant.'}</div>
                  )}
                </div>
                <RequirementBadge status={f.status} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Inspections tab */}
      {tab === 'inspections' && (
        <Section title="INSPECTION RECORDS" onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {(dash?.inspections || []).map((ins) => {
              const isOverdue = ins.status === 'OVERDUE'
              return (
                <div key={ins.id} className="flex items-center justify-between bg-[#0a0e13] border border-steel p-3">
                  <div className="min-w-0">
                    <div className="readout text-[11px] text-slate-200 font-semibold">{ins.inspection_type?.toUpperCase()}</div>
                    <div className="readout text-[9px] text-slate-500 mt-0.5">
                      DUE: {ins.due_date ? formatTime(ins.due_date) : '—'} · LAST: {ins.last_inspection ? formatTime(ins.last_inspection) : 'NEVER'}
                    </div>
                    {ins.status === 'OVERDUE' && <div className="readout text-[9px] text-[#94a3b8] mt-0.5">{ins.evidence}</div>}
                  </div>
                  <span className="readout text-[9px] font-bold px-1.5 py-0.5 shrink-0"
                    style={{ color: isOverdue ? '#ff5a3c' : '#36d17e', border: `1px solid ${isOverdue ? '#ff5a3c' : '#36d17e'}` }}>
                    {ins.status || 'DUE'}
                  </span>
                </div>
              )
            })}
            {(dash?.inspections || []).length === 0 && <div className="readout text-[11px] text-slate-500">NO INSPECTIONS CONFIGURED</div>}
          </div>
        </Section>
      )}

      {/* Open Violations tab */}
      {tab === 'violations' && (
        <Section title="OPEN SAFETY VIOLATIONS" onClose={() => setTab(null)}>
          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {(dash?.policy_violations || []).map((v, i) => {
              const c = v.severity === 'CRITICAL' ? '#ff5a3c' : '#ff7a3c'
              return (
                <div key={i} className="bg-[#0a0e13] border-l-2 border-steel p-3" style={{ borderLeftColor: c }}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="readout text-[9px] font-bold tracking-widest" style={{ color: c }}>{v.severity}</span>
                    <span className="readout text-[9px] text-slate-500">{v.source} · {formatTime(v.timestamp)}</span>
                  </div>
                  <p className="readout text-[10px] text-slate-300">{v.description}</p>
                </div>
              )
            })}
            {(dash?.policy_violations || []).length === 0 && <div className="readout text-[11px] text-slate-500">NO OPEN VIOLATIONS</div>}
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
                  <span className="readout text-[11px] text-slate-200 font-semibold">{r.title}</span>
                  <span className="readout text-[9px] px-1.5 py-0.5 font-bold"
                    style={{ color: r.priority === 'HIGH' ? '#ff7a3c' : r.priority === 'CRITICAL' ? '#ff5a3c' : '#36d17e',
                      border: `1px solid ${r.priority === 'HIGH' ? '#ff7a3c' : r.priority === 'CRITICAL' ? '#ff5a3c' : '#36d17e'}` }}>
                    {r.priority}
                  </span>
                </div>
                <p className="readout text-[10px] text-slate-400 leading-relaxed">{r.description}</p>
                {r.source && <div className="readout text-[9px] text-slate-600 mt-1">SOURCE: {r.source}</div>}
              </div>
            ))}
            {recs.length === 0 && <div className="readout text-[11px] text-slate-500">NO RECOMMENDATIONS</div>}
          </div>
        </Section>
      )}
    </div>
  )
}