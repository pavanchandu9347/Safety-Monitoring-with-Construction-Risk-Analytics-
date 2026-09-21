import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { ReportSections } from '../components/ReportSections'
import {
  BrainCircuit, FileText, AlertTriangle, ShieldAlert, ShieldCheck,
  Activity, Loader2, RefreshCw, Database, ListChecks,
  ChevronDown, ChevronRight, Lightbulb, Download,
} from 'lucide-react'
import { StatChip, Section, ActionBar } from '../components/progressive'

const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const NA = '—'
const fmtScore = (v) => (v == null ? NA : Number(v).toFixed(0))
const levelColor = (l) => LEVEL_HEX[String(l || '').toUpperCase()] || '#6b7d8f'

function FindingRow({ f }) {
  const [open, setOpen] = useState(false)
  const color = levelColor(f.severity)
  return (
    <div className="border border-steel bg-[#0a0e13] mb-2 border-l-2" style={{ borderLeftColor: color }}>
      <button className="w-full flex items-center justify-between px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-2 min-w-0">
          <span className="led" style={{ background: color }} />
          <span className="readout text-[11px] text-slate-200 capitalize truncate">
            [{f.type}] {String(f.title || '').replace(/_/g, ' ')}
          </span>
        </div>
        <span className="flex items-center gap-2 shrink-0">
          <span className="readout text-[9px] font-bold px-1.5 py-0.5" style={{ color, border: `1px solid ${color}` }}>
            {f.severity || 'LOW'}
          </span>
          {open ? <ChevronDown size={13} className="text-slate-500" /> : <ChevronRight size={13} className="text-slate-500" />}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 readout text-[10px] text-slate-400 space-y-1 border-t border-steel-2 pt-2">
          <div>{f.description || 'No description recorded.'}</div>
          {f.worker_name && <div>WORKER: {f.worker_name}</div>}
          {f.zone_name && <div>ZONE: {f.zone_name}</div>}
          {f.hazard_type && <div>TYPE: {String(f.hazard_type).replace(/_/g, ' ')}</div>}
          <div className="text-slate-500">
            ANA {String(f.analysis_id || '').slice(0, 8)} · {f.timestamp ? formatTime(f.timestamp) : '—'}
          </div>
        </div>
      )}
    </div>
  )
}

function ReportView({ report, onClose }) {
  const [text, setText] = useState(null)
  const [loadingText, setLoadingText] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const siteId = report.site_id

  const loadText = async () => {
    setLoadingText(true)
    try {
      const r = await api.getReportText(siteId, report.id)
      setText(r.data.text)
    } finally { setLoadingText(false) }
  }

  const download = async () => {
    setDownloading(true)
    try {
      const r = await api.getReportText(siteId, report.id)
      const blob = new Blob([r.data.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `buildsure-report-${String(report.id).slice(0, 12)}.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } finally { setDownloading(false) }
  }

  return (
    <Section title="REPORT" badge={String(report.report_type || 'risk_intelligence').replace(/_/g, ' ').toUpperCase()} onClose={onClose}>
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="readout text-[10px] text-slate-400">{report.summary}</div>
        <div className="flex items-center gap-2">
          <button onClick={text ? () => setText(null) : loadText} disabled={loadingText}
            className="flex items-center gap-1.5 readout text-[10px] font-bold tracking-wider border border-steel px-2 py-1 text-slate-200 hover:bg-steel">
            <ListChecks size={12} /> {loadingText ? 'LOADING...' : text ? 'VIEW STRUCTURED' : 'VIEW FULL TEXT'}
          </button>
          <button onClick={download} disabled={downloading}
            className="flex items-center gap-1.5 readout text-[10px] font-bold tracking-wider border border-info px-2 py-1 text-info hover:bg-info hover:text-black disabled:opacity-40">
            <Download size={12} /> {downloading ? 'DOWNLOADING...' : 'DOWNLOAD .TXT'}
          </button>
        </div>
      </div>

      {text ? (
        <pre className="readout text-[10px] text-slate-400 whitespace-pre-wrap max-h-[480px] overflow-y-auto border border-steel p-3">{text}</pre>
      ) : (
        <ReportSections report={report} />
      )}
    </Section>
  )
}

export default function Intelligence() {
  const siteId = useSite()
  const [ctx, setCtx] = useState(null)
  const [history, setHistory] = useState({ series: [], trend_available: false })
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [runningAnalysis, setRunningAnalysis] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [detail, setDetail] = useState(null)
  const [report, setReport] = useState(null)
  const [err, setErr] = useState('')
  const [genMsg, setGenMsg] = useState(null)

  const load = async () => {
    setLoading(true); setErr('')
    try {
      const [i, h, reportsRes] = await Promise.all([
        api.getIntelligence(siteId),
        api.getAnalyticsHistory(siteId),
        api.getReports(siteId),
      ])
      setCtx(i.data)
      setHistory(h.data || { series: [], trend_available: false })
      setReports(reportsRes.data.reports || [])
    } catch (e) {
      if (e?.response?.status === 404) setErr('NO ANALYSIS EVIDENCE YET')
      else setErr('INTELLIGENCE UNAVAILABLE')
      setCtx(null); setHistory({ series: [], trend_available: false }); setReports([])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunningAnalysis(true)
    try { await api.analyzeVideo(siteId); await load() } finally { setRunningAnalysis(false) }
  }

  const generate = async () => {
    setGenerating(true)
    setGenMsg(null)
    try {
      const r = await api.generateReport(siteId, { analysisId: ctx?.analysis_id })
      setReports((prev) => [r.data, ...prev.filter((x) => x.id !== r.data.id)])
      setReport(r.data)
      setGenMsg({ type: 'ok', text: 'REPORT GENERATED FROM CURRENT ANALYSIS EVIDENCE.' })
    } catch (e) {
      setGenMsg({
        type: 'err',
        text: e?.response?.status === 404
          ? 'NO ANALYSIS EVIDENCE YET — RUN "ANALYZE SITE VIDEO" FIRST.'
          : e?.response?.data?.detail || 'REPORT GENERATION FAILED.',
      })
    } finally { setGenerating(false) }
  }

  if (loading && !ctx && !err) {
    return <div className="p-8 readout text-slate-400 text-center">LOADING ENTERPRISE INTELLIGENCE...</div>
  }

  const risk = ctx?.overall_risk || {}
  const level = (ctx?.risk_level || 'NOT_AVAILABLE').toUpperCase()
  const color = levelColor(level)

  const chartData = history.series?.map((s) => ({
    time: s.timestamp ? formatTime(s.timestamp) : '—',
    risk: Math.round(s.risk_score ?? 0),
  })).filter((d) => d.risk > 0 || history.series.length > 1)

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit className="text-info" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">ENTERPRISE INTELLIGENCE</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">
            UNIFIED RISK CONTEXT · REPORTING AGENT · HISTORICAL ANALYTICS
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="flex items-center gap-2 border border-steel hover:bg-steel text-slate-200 readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            <RefreshCw size={13} /> REFRESH
          </button>
          <button onClick={generate} disabled={generating || !ctx}
            className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-40 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            <FileText size={13} /> {generating ? 'GENERATING REPORT...' : 'GENERATE REPORT'}
          </button>
        </div>
      </div>

      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      {genMsg && (
        <div className={`tech-panel p-3 border-l-2 ${genMsg.type === 'ok' ? 'border-l-ok' : 'border-l-signal'}`}>
          <p className={`readout text-[11px] font-bold flex items-center gap-2 ${genMsg.type === 'ok' ? 'text-ok' : 'text-signal'}`}>
            <AlertTriangle size={13} /> {genMsg.text}
          </p>
        </div>
      )}

      {err && (
        <div className="tech-panel p-6 text-center readout text-slate-400">
          <div className="text-[13px]">{err}</div>
          <div className="text-[10px] mt-1 text-slate-500">INTELLIGENCE IS DERIVED ONLY FROM REAL ANALYSIS EVIDENCE</div>
          <button onClick={runAnalysis} disabled={runningAnalysis}
            className="mt-4 flex items-center gap-2 mx-auto bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            {runningAnalysis ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            {runningAnalysis ? 'ANALYZING SITE VIDEO...' : 'ANALYZE SITE VIDEO'}
          </button>
        </div>
      )}

      {ctx && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatChip icon={Activity} label="Overall Risk" value={fmtScore(risk.score)} accent={color} sub={level} />
            <StatChip icon={ShieldAlert} label="Critical Findings" value={ctx.critical_findings?.length || 0} accent="#ff5a3c" />
            <StatChip icon={AlertTriangle} label="High Findings" value={ctx.high_findings?.length || 0} accent="#ff7a3c" />
            <StatChip icon={Database} label="Evidence Frames" value={ctx.evidence_summary?.video?.frames_analyzed ?? 0} accent="#4aa8ff" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="tech-panel p-5">
              <div className="bracket-label mb-3 flex items-center gap-1.5"><Activity size={12} /> CURRENT ASSESSMENT</div>
              <div className="text-6xl font-black text-white tabular-nums">{risk.score != null ? risk.score.toFixed(0) : NA}</div>
              <div className="readout text-lg font-bold mt-1" style={{ color }}>{level}</div>
              <div className="mt-4 space-y-1">
                {[['environmental', 'ENVIRONMENTAL'], ['equipment', 'EQUIPMENT'], ['site_condition', 'SITE CONDITION'], ['activity', 'ACTIVITY']].map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between readout text-[10px] text-slate-400">
                    <span className="tracking-widest">{label}</span>
                    <span className="text-slate-200 font-bold tabular-nums">{risk[`${key}_score`] != null ? Math.round(risk[`${key}_score`]) : NA}</span>
                  </div>
                ))}
              </div>
              <p className="readout text-[10px] text-slate-400 border-t border-steel pt-3 mt-3 leading-relaxed">
                {risk.summary ? risk.summary.toLowerCase() : 'No video-derived contributing factors were recorded for this analysis.'}
              </p>
            </div>

            <div className="lg:col-span-2 tech-panel p-4">
              <div className="bracket-label mb-2">HISTORICAL ANALYTICS · RISK TREND</div>
              {history.trend_available && history.series.length > 1 ? (
                chartData.length > 0 ? (
                  <div className="space-y-0">
                    {chartData.map((d, i) => (
                      <div key={i} className="flex items-center gap-2 readout text-[10px] text-slate-400">
                        <span className="w-24 truncate">{d.time}</span>
                        <div className="flex-1 h-2 bg-[#0a0e13] border border-steel overflow-hidden">
                          <div className="h-full bg-hazard" style={{ width: `${Math.min(100, d.risk)}%` }} />
                        </div>
                        <span className="w-8 text-right text-slate-200 font-bold">{d.risk}</span>
                      </div>
                    ))}
                    <div className="readout text-[9px] text-slate-500 mt-2">
                      {history.series.length} REAL ANALYSES · TREND FROM PERSISTED EVIDENCE ONLY
                    </div>
                  </div>
                ) : (
                  <div className="readout text-slate-500 text-center py-12 text-[11px]">NO SCORED ANALYSES YET</div>
                )
              ) : (
                <div className="readout text-slate-500 text-center py-12 text-[11px]">
                  {history.message || 'INSUFFICIENT_DATA'}
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="bracket-label mb-2 flex items-center gap-1.5"><BrainCircuit size={12} /> INTELLIGENCE VIEWS</div>
            <ActionBar
              active={detail}
              onToggle={(k) => { setDetail(detail === k ? null : k); if (k !== 'reports') setReport(null) }}
              items={[
                { key: 'findings', label: 'Findings', icon: AlertTriangle },
                { key: 'safety', label: 'Safety', icon: ShieldCheck },
                { key: 'compliance', label: 'Compliance', icon: ShieldCheck },
                { key: 'insurance', label: 'Insurance', icon: FileText },
                { key: 'actions', label: 'Actions', icon: ListChecks },
                { key: 'evidence', label: 'Evidence', icon: Database },
              ]}
            />
          </div>

          {detail === 'findings' && (
            <Section title="CRITICAL & HIGH FINDINGS" badge={`${(ctx.critical_findings?.length || 0) + (ctx.high_findings?.length || 0)} FINDINGS`} onClose={() => setDetail(null)}>
              {!ctx.critical_findings?.length && !ctx.high_findings?.length && (
                <div className="readout text-slate-500 text-center py-6 text-[11px]">NO HIGH OR CRITICAL FINDINGS IN THIS ANALYSIS</div>
              )}
              {ctx.critical_findings?.length > 0 && (
                <>
                  <div className="bracket-label text-[10px] mb-1 text-signal">CRITICAL</div>
                  {ctx.critical_findings.map((f, i) => <FindingRow key={i} f={f} />)}
                </>
              )}
              {ctx.high_findings?.length > 0 && (
                <>
                  <div className="bracket-label text-[10px] mb-1 text-hazard mt-3">HIGH</div>
                  {ctx.high_findings.map((f, i) => <FindingRow key={i} f={f} />)}
                </>
              )}
            </Section>
          )}

          {detail === 'safety' && (
            <Section title="SAFETY INTELLIGENCE" onClose={() => setDetail(null)}>
              <SafetyView ctx={ctx} />
            </Section>
          )}

          {detail === 'compliance' && (
            <Section title="COMPLIANCE INTELLIGENCE" onClose={() => setDetail(null)}>
              <ComplianceView ctx={ctx} />
            </Section>
          )}

          {detail === 'insurance' && (
            <Section title="INSURANCE INTELLIGENCE" onClose={() => setDetail(null)}>
              <InsuranceView ctx={ctx} />
            </Section>
          )}

          {detail === 'actions' && (
            <Section title="PRIORITIZED ACTIONS" badge={`${ctx.recommendations?.length || 0} ACTIONS`} onClose={() => setDetail(null)}>
              {!ctx.recommendations?.length && <div className="readout text-slate-500 text-center py-6 text-[11px]">NO PERSISTED RECOMMENDATIONS FOR THIS ANALYSIS</div>}
              <div className="max-h-[420px] overflow-y-auto space-y-1">
                {ctx.recommendations.map((r, i) => {
                  const c = levelColor(r.priority)
                  return (
                    <div key={i} className="border border-steel bg-[#0a0e13] p-3 border-l-2" style={{ borderLeftColor: c }}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="readout text-[10px] font-bold tracking-widest" style={{ color: c }}>{r.priority || 'MEDIUM'}</span>
                        <span className="readout text-[9px] text-slate-500 uppercase">{r.source}</span>
                      </div>
                      <div className="text-[12px] text-white font-semibold mt-1 readout">{r.title}</div>
                      {r.description && <p className="text-[10px] text-slate-400 mt-1 readout">{r.description}</p>}
                    </div>
                  )
                })}
              </div>
            </Section>
          )}

          {detail === 'evidence' && (
            <Section title="EVIDENCE & DATA QUALITY" onClose={() => setDetail(null)}>
              <EvidenceView ctx={ctx} />
            </Section>
          )}

          <div className="tech-panel p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="bracket-label">GENERATED REPORTS</span>
              <button onClick={generate} disabled={generating || !ctx}
                className="flex items-center gap-2 readout text-[10px] font-bold tracking-wider border border-hazard text-hazard hover:bg-hazard hover:text-black px-2 py-1 transition disabled:opacity-40">
                <FileText size={12} /> {generating ? 'GENERATING...' : 'GENERATE REPORT'}
              </button>
            </div>
            {!reports.length && <div className="readout text-slate-500 text-center py-6 text-[11px]">NO REPORTS GENERATED YET — REPORTS ARE BUILT ONLY FROM REAL ANALYSIS EVIDENCE</div>}
            <div className="space-y-1">
              {reports.map((r) => (
                <button key={r.id} onClick={() => setReport(report?.id === r.id ? null : r)}
                  className="w-full text-left flex items-center justify-between gap-2 border border-steel bg-[#0a0e13] px-3 py-2 hover:bg-[#151b23] transition">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={13} className="text-info shrink-0" />
                    <div className="readout min-w-0">
                      <div className="text-[11px] text-slate-200 truncate">{r.title || 'Risk Intelligence Report'} · {String(r.id || '').slice(0, 8)}</div>
                      <div className="text-[9px] text-slate-500 truncate">{r.summary}</div>
                    </div>
                  </div>
                  <span className="readout text-[9px] text-slate-500 shrink-0">ANA {String(r.analysis_id || '').slice(0, 8) || '—'} · {r.created_at ? formatTime(r.created_at) : '—'}</span>
                </button>
              ))}
            </div>
            {report && <div className="mt-3"><ReportView report={report} onClose={() => setReport(null)} /></div>}
          </div>
        </>
      )}
    </div>
  )
}

function SafetyView({ ctx }) {
  const s = ctx.safety_summary || {}
  const ws = ctx.worker_summary || {}
  const pp = ctx.ppe_summary || {}
  const score = s.overall_safety_score
  const color = levelColor(s.overall_safety_level)
  return (
    <div className="space-y-3">
      {score == null ? (
        <div className="readout text-slate-500 text-center py-6 text-[11px]">SAFETY INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <StatChip icon={ShieldCheck} label="Safety" value={fmtScore(score)} accent={color} sub={s.overall_safety_level || NA} />
          <StatChip icon={Lightbulb} label="PPE Compliance" value={s.ppe_compliance_rate != null ? `${(s.ppe_compliance_rate * 100).toFixed(0)}%` : NA} accent="#36d17e" />
          <StatChip icon={ShieldAlert} label="Workers" value={ws.total ?? 0} accent="#4aa8ff" />
          <StatChip icon={AlertTriangle} label="Violations" value={s.violation_count ?? 0} accent="#f5a623" />
        </div>
      )}
      {s.summary && <div className="readout text-[11px] text-slate-300">{s.summary}</div>}
      {ws.missing_ppe?.length > 0 && (
        <div className="tech-panel p-3">
          <div className="bracket-label text-[10px]">WORKERS MISSING PPE</div>
          <div className="mt-1 space-y-1">
            {ws.missing_ppe.map((w, i) => (
              <div key={i} className="readout text-[11px] text-slate-300">
                {w.worker_name || w.worker_id} — {w.missing_ppe.join(', ')}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="readout text-[10px] text-slate-500">
        HELMET {pp.helmet_violations ?? 0} · VEST {pp.vest_violations ?? 0} · OTHER {pp.other_violations ?? 0} · TOTAL {pp.total_violations ?? 0}
      </div>
    </div>
  )
}

function ComplianceView({ ctx }) {
  const c = ctx.compliance_summary
  const level = c?.compliance_level || 'NOT_AVAILABLE'
  return (
    <div className="space-y-3">
      {!c ? (
        <div className="readout text-slate-500 text-center py-6 text-[11px]">COMPLIANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <StatChip icon={ShieldCheck} label="Level" value={level} accent={levelColor(level)} />
            <StatChip icon={ShieldCheck} label="Checked" value={c.requirements_checked ?? 0} accent="#4aa8ff" />
            <StatChip icon={AlertTriangle} label="Non-Compliant" value={c.non_compliant_count ?? 0} accent="#ff5a3c" />
            <StatChip icon={Database} label="Not Verified" value={c.not_verified_count ?? 0} accent="#6b7d8f" />
          </div>
          <div className="readout text-[10px] text-slate-500">
            {c.score_basis || 'NOT_VERIFIED FINDINGS ARE NEVER COUNTED AS NON-COMPLIANT'}
          </div>
          {c.summary && <div className="readout text-[11px] text-slate-300">{c.summary}</div>}
        </>
      )}
    </div>
  )
}

function InsuranceView({ ctx }) {
  const ins = ctx.insurance_summary
  const incidents = ctx.insurance_incidents || []
  const claims = ctx.claim_records || []
  return (
    <div className="space-y-3">
      {!ins ? (
        <div className="readout text-slate-500 text-center py-6 text-[11px]">INSURANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <StatChip icon={FileText} label="Risk" value={fmtScore(ins.risk_score)} accent={levelColor(ins.risk_level)} sub={ins.risk_level || NA} />
            <StatChip icon={AlertTriangle} label="Open Incidents" value={ins.open_incidents ?? 0} accent="#f5a623" />
            <StatChip icon={Lightbulb} label="Verified Incidents" value={incidents.length} accent="#ff7a3c" />
            <StatChip icon={FileCheck2} label="Claim Records" value={claims.length} accent="#4aa8ff" />
          </div>
          {ins.summary && <div className="readout text-[11px] text-slate-300">{ins.summary}</div>}
          {claims.length === 0 && (
            <div className="readout text-[9px] text-slate-500">NO INSURANCE CLAIMS ARE INVENTED — NONE ON RECORD FOR THIS ANALYSIS</div>
          )}
        </>
      )}
    </div>
  )
}

function EvidenceView({ ctx }) {
  const ev = ctx.evidence_summary || {}
  const video = ev.video || {}
  const counts = ev.counts || {}
  const dq = ctx.data_quality || {}
  const rows = [
    ['Video', video.filename || NA],
    ['Frames Analyzed', video.frames_analyzed ?? 0],
    ['Model', video.model_used || NA],
    ['Hazards', counts.hazards ?? 0],
    ['Violations', counts.safety_violations ?? 0],
    ['Alerts', counts.safety_alerts ?? 0],
    ['Workers', counts.workers ?? 0],
    ['Equipment', counts.equipment ?? 0],
    ['Compliance Findings', counts.compliance_findings ?? 0],
    ['Incidents', counts.insurance_incidents ?? 0],
    ['Claim Records', counts.claim_records ?? 0],
  ]
  return (
    <div className="space-y-3">
      <div className={`readout text-[10px] px-3 py-2 border ${dq.status === 'COMPLETE' ? 'border-ok text-ok' : 'border-hazard text-hazard'}`}>
        DATA QUALITY: {dq.status}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between readout text-[10px] text-slate-400 border-b border-steel-2/40 py-1">
            <span>{k.toUpperCase()}</span>
            <span className="text-slate-200 font-bold tabular-nums">{v}</span>
          </div>
        ))}
      </div>
      <div className="readout text-[9px] text-slate-500">{dq.note}</div>
    </div>
  )
}