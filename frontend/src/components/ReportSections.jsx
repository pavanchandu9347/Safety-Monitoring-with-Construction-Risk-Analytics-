import { useState } from 'react'
import {
  Building2, FileSearch, Activity, ShieldCheck, ShieldAlert, Umbrella,
  AlertTriangle, Lightbulb, History, Database, Info, Clock, HardHat,
  Wrench, Diamond, ChevronDown, ChevronRight, Bell, ListChecks,
} from 'lucide-react'
import { Gauge, Donut, Bars, TrendChart, EmptyState, ExpandCard, sevColor } from './visuals'

const NA = '—'
const fmtScore = (v) => (v == null ? NA : Number(v).toFixed(0))
const shortId = (v) => (v ? String(v).slice(0, 12) : NA)
const clean = (s) => String(s || '').replace(/_/g, ' ').toUpperCase()

const DIM_COLOR = {
  ENVIRONMENTAL: '#4aa8ff',
  EQUIPMENT: '#f5a623',
  'SITE CONDITION': '#36d17e',
  ACTIVITY: '#b794ff',
}

function SevDot({ level }) {
  const c = sevColor(level)
  return <span className="flex items-center gap-1.5 readout text-[8px] tracking-[0.15em] font-bold" style={{ color: c }}>
    <span className="w-2 h-2 rounded-full" style={{ background: c, boxShadow: `0 0 6px ${c}` }} />{clean(level)}
  </span>
}

function K({ k, v, accent }) {
  return (
    <div className="flex items-center justify-between gap-3 readout text-[10px] text-slate-400 border-b border-steel-2/40 py-1.5 last:border-0">
      <span className="tracking-widest">{k}</span>
      <span className="font-bold tabular-nums text-right" style={{ color: accent || 'var(--color-ink)' }}>{v}</span>
    </div>
  )
}

function Chip({ icon: Icon, label, value, accent }) {
  return (
    <div className="flex items-center gap-2 bg-[#0a0e13] border border-steel px-2.5 py-1.5">
      <Icon size={12} style={{ color: accent || '#4aa8ff' }} />
      <span className="readout text-[8px] tracking-widest text-slate-500">{label}</span>
      <span className="readout text-[11px] font-bold tabular-nums" style={{ color: accent || 'var(--color-ink)' }}>{value}</span>
    </div>
  )
}

/* Compact severity finding row with optional "View Details". */
function FindingCard({ f }) {
  const [open, setOpen] = useState(false)
  const color = sevColor(f.severity)
  return (
    <div className="border border-steel bg-[#0a0e13] border-l-2" style={{ borderLeftColor: color }}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
          <span className="readout text-[11px] text-slate-200 truncate">
            {clean(f.severity)} · {String(f.title || f.hazard_type || f.type || 'Finding').replace(/_/g, ' ')}
          </span>
        </div>
        <span className="readout text-[8px] tracking-widest text-info flex items-center gap-1 shrink-0">
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />} {open ? 'HIDE' : 'VIEW DETAILS'}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-steel-2/60 pt-2 space-y-0.5 readout text-[10px] text-slate-400">
          {f.description && <div>{f.description}</div>}
          {f.type && <div>TYPE: {clean(f.type)}</div>}
          {f.hazard_type && <div>CATEGORY: {clean(f.hazard_type)}</div>}
          {f.worker_name && <div>WORKER: {f.worker_name}</div>}
          {f.zone_name && <div>ZONE: {f.zone_name}</div>}
          <div className="text-slate-500">EVIDENCE: ANA {shortId(f.analysis_id)} {f.timestamp ? `· ${String(f.timestamp).replace('T', ' ').slice(0, 19)}` : ''}</div>
        </div>
      )}
    </div>
  )
}

/* Recommendation card: Issue → Action → Priority. */
function ActionCard({ a }) {
  const color = sevColor(a.priority)
  return (
    <div className="border border-steel bg-[#0a0e13] border-l-2 px-3 py-2" style={{ borderLeftColor: color }}>
      <div className="flex items-center justify-between gap-2">
        <span className="readout text-[9px] font-bold tracking-widest" style={{ color }}>{clean(a.priority)}</span>
        {a.source && <span className="readout text-[8px] tracking-widest text-slate-500 uppercase">{a.source}</span>}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-1.5 gap-y-0.5 readout text-[10px] text-slate-300">
        <span className="text-slate-500 tracking-widest">ISSUE</span> <span>{a.title}</span>
        {a.description && <>
          <span className="text-slate-600">→</span>
          <span className="text-slate-500 tracking-widest">ACTION</span> <span>{a.description}</span>
        </>}
      </div>
    </div>
  )
}

function ScoreRow({ items }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.map((it, i) => (
        <div key={i} className="bg-[#0a0e13] border border-steel p-3 flex flex-col items-center justify-center">
          <Gauge value={it.value} color={it.color} label={it.sub} size={76} />
          <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mt-1.5 text-center">{it.label}</div>
          {it.sub && <div className="readout text-[8px] font-bold tracking-widest mt-0.5" style={{ color: it.color }}>{it.sub}</div>}
        </div>
      ))}
    </div>
  )
}

function exposureBars(exposure) {
  if (!exposure || typeof exposure !== 'object') return []
  const entries = Object.entries(exposure)
  const out = []
  const hasFlatNumeric = entries.some(([, v]) => typeof v === 'number')
  for (const [k, v] of entries) {
    if (k === 'overall' && typeof v === 'object') continue
    let n = v
    if (hasFlatNumeric && typeof v !== 'number') continue
    if (!hasFlatNumeric && v && typeof v === 'object' && 'score' in v) n = v.score
    const num = Number(n)
    if (Number.isFinite(num) && !['overall', 'evidence_available'].includes(k)) {
      out.push({ label: clean(k), value: Math.round(num), color: '#ff7a3c' })
    }
  }
  return out.slice(0, 8)
}

/* Structured, visual rendering of the executive report. history =
   { series:[{timestamp,risk_score}], trend_available, message } (real analytics). */
export function ReportSections({ report, history }) {
  const content = report?.content || {}
  const site = content.site_info || {}
  const an = content.analysis_info || {}
  const exec = content.executive_summary || {}
  const sections = content.sections || {}
  const risk = sections.risk || {}
  const safety = sections.safety || {}
  const compliance = sections.compliance || {}
  const insurance = sections.insurance || {}
  const srisk = risk.site_risk || {}
  const hist = history || content.historical_analytics || {}
  const evidence = content.evidence_summary || {}
  const dq = evidence.data_quality || content.data_quality || {}
  const counts = evidence.counts || {}
  const findings = [...(content.critical_findings || []), ...(content.high_findings || [])]
  const actions = content.prioritized_actions || []

  const [showAllFindings, setShowAllFindings] = useState(false)
  const [showAllActions, setShowAllActions] = useState(false)

  const scored = ((hist.series || []).map((s) => ({ ...s, value: s.risk_score }))).filter((s) => s.risk_score != null)
  const trendData = scored.length >= 2 ? scored.map((s) => ({ label: s.timestamp ? String(s.timestamp).replace('T', ' ').slice(11, 16) : '—', value: Math.round(s.risk_score) })) : null

  const catCounts = Object.entries((findings || []).reduce((m, f) => {
    const k = String(f.hazard_type || f.type || f.title || 'other').replace(/_/g, ' ').toUpperCase()
    return (m[k] = (m[k] || 0) + 1, m)
  }, {}))
  const catBars = catCounts.map(([label, value]) => ({ label, value, color: DIM_COLOR[label] || '#ff7a3c' })).slice(0, 6)

  const compBars = (risk.components || []).map((c) => ({
    label: c.label, value: Math.round(c.score || 0), color: DIM_COLOR[c.label] || '#4aa8ff',
  }))

  let compSlices = null
  if (compliance.status !== 'NOT_AVAILABLE') {
    const cd = [
      { label: 'COMPLIANT', value: compliance.compliant_count || 0, color: '#36d17e' },
      { label: 'NON-COMPLIANT', value: compliance.non_compliant_count || 0, color: '#ff5a3c' },
      { label: 'NOT VERIFIED', value: compliance.not_verified_count || 0, color: '#6b7d8f' },
    ]
    if (cd.some((c) => c.value > 0)) compSlices = cd
  }

  let ppeSlices = null
  if (safety.ppe_compliance_rate != null) {
    const p = Math.round(safety.ppe_compliance_rate * 100)
    ppeSlices = [
      { label: 'COMPLIANT', value: p, color: '#36d17e' },
      { label: 'NON-COMPLIANT', value: 100 - p, color: '#ff5a3c' },
    ]
  }

  const exBars = exposureBars(insurance.exposure)

  const sevCounts = Object.entries(srisk.hazards_by_severity || {})
    .map(([k, v]) => ({ level: k, value: v }))
    .filter((s) => Number(s.value) > 0)

  return (
    <div className="space-y-3">
      {/* 01 Executive punch: score gauges */}
      <div className="tech-panel p-4">
        <div className="bracket-label mb-3 flex items-center gap-2"><Activity size={13} className="text-info" /> EXECUTIVE RISK SUMMARY</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          <Chip icon={Building2} label="SITE" value={site.site_name || site.site_id || NA} />
          <Chip icon={FileSearch} label="VIDEO" value={an.video_source || NA} accent="#4aa8ff" />
          <Chip icon={Clock} label="FRAMES" value={an.frames_analyzed ?? NA} accent="#f5a623" />
          <Chip icon={History} label="TREND" value={clean(exec.risk_trend_direction || 'INSUFFICIENT_DATA')} accent={sevColor(exec.risk_trend_direction)} />
        </div>
        <ScoreRow items={[
          { label: 'OVERALL RISK', value: risk.overall_score, color: sevColor(risk.risk_level), sub: risk.risk_level },
          { label: 'SAFETY', value: safety.status === 'NOT_AVAILABLE' ? null : safety.overall_safety_score, color: sevColor(safety.overall_safety_level), sub: safety.overall_safety_level },
          { label: 'COMPLIANCE', value: compliance.status === 'NOT_AVAILABLE' ? null : compliance.overall_score, color: sevColor(compliance.compliance_level), sub: compliance.compliance_level },
          { label: 'INSURANCE RISK', value: insurance.status === 'NOT_AVAILABLE' ? null : insurance.risk_score, color: sevColor(insurance.risk_level), sub: insurance.risk_level },
        ]} />
        <p className="readout text-[10px] text-slate-400 mt-3">{exec.short_line || exec.response || 'Risk report generated from persisted analysis evidence.'}</p>
        {(exec.key_concerns || []).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(exec.key_concerns || []).map((c, i) => (
              <span key={i} className="readout text-[9px] px-1.5 py-0.5 border border-[#ff7a3c]/40 bg-[#ff7a3c]/10 text-slate-300">! {c}</span>
            ))}
          </div>
        )}
      </div>

      {/* 02 Risk Analytics */}
      <ExpandCard title="RISK ANALYTICS" badge={`LEVEL ${risk.risk_level || 'NOT_AVAILABLE'}`} icon={Activity} defaultOpen>
        {risk.status === 'NOT_AVAILABLE' || risk.overall_score == null ? (
          <EmptyState msg="RISK INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS" />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="flex flex-col items-center justify-center">
              <Gauge value={risk.overall_score} color={sevColor(risk.risk_level)} sub={risk.risk_level} size={120} />
              <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mt-2">OVERALL RISK SCORE</div>
            </div>
            <div className="lg:col-span-2 space-y-2">
              <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mb-1">RISK DISTRIBUTION · COMPONENTS</div>
              <Bars items={compBars} />
            </div>
          </div>
        )}
        {sevCounts.length > 0 && (
          <div className="mt-3 pt-3 border-t border-steel/60">
            <span className="readout text-[8px] tracking-[0.2em] text-slate-500 mr-4">HAZARDS BY SEVERITY</span>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
              {sevCounts.map((s, i) => (
                <span key={i} className="flex items-center gap-1.5 readout text-[10px] font-bold" style={{ color: sevColor(s.level) }}>
                  <span className="w-2 h-2 rounded-full" style={{ background: sevColor(s.level), boxShadow: `0 0 6px ${sevColor(s.level)}` }} />
                  {s.value} {clean(s.level)}
                </span>
              ))}
            </div>
          </div>
        )}
      </ExpandCard>

      {/* 03 Safety */}
      <ExpandCard title="SAFETY INTELLIGENCE" badge={`SCORE ${fmtScore(safety.overall_safety_score)}`} icon={HardHat}>
        {safety.status === 'NOT_AVAILABLE' || safety.overall_safety_score == null ? (
          <EmptyState msg="SAFETY INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Chip icon={HardHat} label="WORKERS" value={safety.worker_count ?? 0} accent="#4aa8ff" />
                <Chip icon={ShieldAlert} label="VIOLATIONS" value={safety.violation_count ?? 0} accent="#f5a623" />
                <Chip icon={Bell} label="ALERTS" value={safety.alert_count ?? 0} accent="#ff7a3c" />
                <Chip icon={ShieldCheck} label="PPE COMPLIANCE" value={safety.ppe_compliance_rate != null ? `${(safety.ppe_compliance_rate * 100).toFixed(0)}%` : NA} accent="#36d17e" />
              </div>
              {catBars.length > 0 && (
                <div>
                  <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mb-1 mt-2">FINDINGS BY CATEGORY</div>
                  <Bars items={catBars} />
                </div>
              )}
            </div>
            <div className="flex flex-col items-center justify-center">
              {ppeSlices ? (
                <Donut slices={ppeSlices} center={`${(safety.ppe_compliance_rate * 100).toFixed(0)}%`} centerAdult="PPE COMPLIANCE" />
              ) : (
                <EmptyState msg="PPE COMPLIANCE NOT AVAILABLE" />
              )}
            </div>
          </div>
        )}
      </ExpandCard>

      {/* 04 Compliance */}
      <ExpandCard title="COMPLIANCE INTELLIGENCE" badge={`LEVEL ${clean(compliance.compliance_level)}`} icon={ListChecks}>
        {compliance.status === 'NOT_AVAILABLE' ? (
          <EmptyState msg="COMPLIANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="grid grid-cols-2 gap-2 self-start">
              <Chip icon={ListChecks} label="CHECKED" value={compliance.requirements_checked ?? 0} accent="#4aa8ff" />
              <Chip icon={ShieldCheck} label="COMPLIANT" value={compliance.compliant_count ?? 0} accent="#36d17e" />
              <Chip icon={AlertTriangle} label="NON-COMPLIANT" value={compliance.non_compliant_count ?? 0} accent="#ff5a3c" />
              <Chip icon={Info} label="NOT VERIFIED" value={compliance.not_verified_count ?? 0} accent="#6b7d8f" />
              {compliance.overdue_inspections != null && (
                <Chip icon={Clock} label="OVERDUE" value={compliance.overdue_inspections} accent="#ff7a3c" />
              )}
            </div>
            <div className="flex flex-col items-center justify-center">
              {compSlices ? (
                <Donut slices={compSlices} center={compliance.requirements_checked ?? 0} centerAdult="REQUIREMENTS CHECKED" />
              ) : (
                <EmptyState msg="NO REQUIREMENT STATUS RECORDS" />
              )}
              <div className="readout text-[8px] text-slate-500 tracking-wider mt-1">NOT VERIFIED ≠ NON-COMPLIANT</div>
            </div>
          </div>
        )}
      </ExpandCard>

      {/* 05 Insurance */}
      <ExpandCard title="INSURANCE INTELLIGENCE" badge={`RISK ${clean(insurance.risk_level)}`} icon={Umbrella}>
        {insurance.status === 'NOT_AVAILABLE' ? (
          <EmptyState msg="INSURANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <Chip icon={Umbrella} label="OPEN INCIDENTS" value={insurance.open_incidents ?? 0} accent="#f5a623" />
                <Chip icon={AlertTriangle} label="VERIFIED" value={insurance.verified_incidents?.length ?? 0} accent="#ff7a3c" />
                <Chip icon={FileSearch} label="CLAIM RECORDS" value={insurance.claim_records ?? 0} accent="#4aa8ff" />
                {insurance.incident_severity && <Chip icon={Diamond} label="SEVERITY" value={clean(insurance.incident_severity)} accent={sevColor(insurance.incident_severity)} />}
              </div>
              {(insurance.verified_incidents || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {insurance.verified_incidents.map((t, i) => (
                    <span key={i} className="readout text-[8px] px-1.5 py-0.5 border border-steel-2 text-slate-400">{clean(t)}</span>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mb-1">EXPOSURE BY CATEGORY</div>
              {exBars.length > 0 ? <Bars items={exBars} /> : <EmptyState msg="NO EXPOSURE CATEGORY RECORDS" />}
            </div>
          </div>
        )}
      </ExpandCard>

      {/* 06 Critical findings */}
      <ExpandCard title="CRITICAL FINDINGS" badge={`${findings.length} FINDINGS`} icon={AlertTriangle} defaultOpen>
        {findings.length === 0 ? (
          <EmptyState msg="NO HIGH OR CRITICAL FINDINGS IN THIS ANALYSIS" />
        ) : (
          <>
            <div className="space-y-1.5">
              {(showAllFindings ? findings : findings.slice(0, 4)).map((f, i) => <FindingCard key={i} f={f} />)}
            </div>
            {findings.length > 4 && (
              <button onClick={() => setShowAllFindings(!showAllFindings)}
                className="mt-2 readout text-[9px] tracking-widest text-info hover:text-white flex items-center gap-1">
                {showAllFindings ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                {showAllFindings ? 'SHOW LESS' : `VIEW ALL (${findings.length})`}
              </button>
            )}
          </>
        )}
      </ExpandCard>

      {/* 07 Recommendations */}
      <ExpandCard title="RECOMMENDATIONS" badge={`${actions.length} ACTIONS`} icon={Lightbulb}>
        {actions.length === 0 ? (
          <EmptyState msg="NO PERSISTED RECOMMENDATIONS FOR THIS ANALYSIS" />
        ) : (
          <>
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
              {(showAllActions ? actions : actions.slice(0, 5)).map((a, i) => <ActionCard key={i} a={a} />)}
            </div>
            {actions.length > 5 && (
              <button onClick={() => setShowAllActions(!showAllActions)}
                className="mt-2 readout text-[9px] tracking-widest text-info hover:text-white flex items-center gap-1">
                {showAllActions ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                {showAllActions ? 'SHOW LESS' : `SHOW MORE (${actions.length})`}
              </button>
            )}
          </>
        )}
      </ExpandCard>

      {/* 08 Historical analytics */}
      <ExpandCard title="HISTORICAL ANALYTICS" badge={hist.trend_available ? clean(hist.direction) : 'NO HISTORY'} icon={History}>
        {trendData ? (
          <div>
            <TrendChart data={trendData} />
            <div className="readout text-[9px] text-slate-500 mt-1">{hist.message || `${scored.length} REAL ANALYSES`}</div>
          </div>
        ) : (
          <div>
            <EmptyState icon={History} msg="HISTORICAL DATA NOT AVAILABLE FOR THIS SITE" compact />
            {hist.message && <div className="readout text-[9px] text-slate-500 text-center pb-2">{hist.message}</div>}
          </div>
        )}
      </ExpandCard>

      {/* 09 Evidence */}
      <ExpandCard title="EVIDENCE & DATA QUALITY" badge={`QUALITY ${clean(dq.status)}`} icon={Database}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mb-1.5">EVIDENCE SOURCE</div>
            <div className="space-y-1">
              <K k="VIDEO SOURCE" v={an.video_source || NA} />
              <K k="FRAMES ANALYZED" v={an.frames_analyzed ?? NA} />
              <K k="MODEL" v={clean(an.model_used)} />
              <K k="ANALYSIS" v={shortId(content.analysis_id || report?.analysis_id)} />
              {dq.insufficient_dimensions?.length > 0 && (
                <K k="INSUFFICIENT EVIDENCE" v={clean(dq.insufficient_dimensions.join(', '))} accent="#6b7d8f" />
              )}
            </div>
          </div>
          <div>
            <div className="readout text-[8px] tracking-[0.2em] text-slate-500 mb-1.5">PERSISTED COUNTS</div>
            <div className="flex flex-wrap gap-1.5">
              {counts.hazards != null && <Chip icon={ShieldAlert} label="HAZARDS" value={counts.hazards} accent="#ff7a3c" />}
              {counts.workers != null && <Chip icon={HardHat} label="WORKERS" value={counts.workers} accent="#4aa8ff" />}
              {counts.equipment != null && <Chip icon={Wrench} label="EQUIPMENT" value={counts.equipment} accent="#f5a623" />}
              {counts.safety_violations != null && <Chip icon={AlertTriangle} label="VIOLATIONS" value={counts.safety_violations} accent="#f5a623" />}
              {counts.safety_alerts != null && <Chip icon={Bell} label="ALERTS" value={counts.safety_alerts} accent="#ff7a3c" />}
              {counts.compliance_findings != null && <Chip icon={ListChecks} label="COMPLIANCE" value={counts.compliance_findings} accent="#4aa8ff" />}
              {counts.insurance_incidents != null && <Chip icon={Umbrella} label="INCIDENTS" value={counts.insurance_incidents} accent="#ff7a3c" />}
              {counts.claim_records != null && <Chip icon={FileSearch} label="CLAIMS" value={counts.claim_records} accent="#4aa8ff" />}
            </div>
            {dq.note && <div className="readout text-[9px] text-slate-500 mt-2">{dq.note}</div>}
          </div>
        </div>
      </ExpandCard>

      {/* 10 Limitations (short, factual) */}
      <ExpandCard title="LIMITATIONS" icon={Info}>
        <ul className="space-y-1">
          {(content.limitations || []).length === 0 ? (
            <li className="readout text-[10px] text-slate-400">No recorded limitations for this analysis.</li>
          ) : (
            (content.limitations || []).map((l, i) => <li key={i} className="readout text-[10px] text-slate-400">• {l}</li>)
          )}
        </ul>
      </ExpandCard>

      <div className="readout text-[9px] text-slate-600 flex items-center gap-1.5 justify-center">
        <ShieldCheck size={11} /> ALL VALUES DERIVED FROM PERSISTED ANALYSIS EVIDENCE — NOTHING IS FABRICATED
      </div>
    </div>
  )
}