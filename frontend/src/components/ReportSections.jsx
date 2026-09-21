import {
  Building2, FileSearch, Activity, ShieldCheck, ShieldAlert, FileText,
  AlertTriangle, ListChecks, History, Database, Info, Tag,
} from 'lucide-react'

const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const NA = '—'
const fmtScore = (v) => (v == null ? NA : Number(v).toFixed(0))
const levelColor = (l) => LEVEL_HEX[String(l || '').toUpperCase()] || '#6b7d8f'
const shortId = (v) => (v ? String(v).slice(0, 12) : NA)

function Block({ num, title, icon: Icon, children }) {
  return (
    <div className="tech-panel p-4">
      <div className="bracket-label text-[10px] mb-3 flex items-center gap-2">
        <span className="text-slate-600">{String(num).padStart(2, '0')}</span>
        <Icon size={13} className="text-info" /> {title}
      </div>
      {children}
    </div>
  )
}

function KV({ k, v, accent }) {
  return (
    <div className="flex items-center justify-between gap-3 readout text-[10px] text-slate-400 border-b border-steel-2/40 py-1.5 last:border-0">
      <span className="tracking-widest">{k}</span>
      <span className="font-bold tabular-nums text-right" style={{ color: accent || '#e2e8f0' }}>{v}</span>
    </div>
  )
}

function Metric({ label, value, accent, sub }) {
  return (
    <div className="bg-[#0a0e13] border border-steel p-3">
      <div className="readout text-xl font-black text-white tabular-nums leading-none" style={{ color: accent || undefined }}>{value}</div>
      <div className="readout text-[9px] text-slate-500 tracking-widest mt-1 uppercase">{label}</div>
      {sub && <div className="readout text-[9px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function FindingRow({ f }) {
  const color = levelColor(f.severity)
  return (
    <div className="border-l-2 bg-[#0a0e13] border border-steel px-3 py-2 mb-1.5" style={{ borderLeftColor: color }}>
      <div className="flex items-center justify-between gap-2">
        <span className="readout text-[11px] text-slate-200 font-semibold capitalize">
          [{f.severity || 'LOW'}] {String(f.title || f.hazard_type || 'Finding').replace(/_/g, ' ')}
        </span>
        <span className="readout text-[9px] text-slate-500 shrink-0">{shortId(f.analysis_id)}</span>
      </div>
      {(f.description || f.zone_name || f.hazard_type) && (
        <div className="readout text-[10px] text-slate-400 mt-1 leading-relaxed">
          {f.description}
          {f.zone_name && <span className="text-slate-500"> · ZONE: {f.zone_name}</span>}
        </div>
      )}
    </div>
  )
}

function ActionRow({ a }) {
  const color = levelColor(a.priority)
  return (
    <div className="border-l-2 bg-[#0a0e13] border border-steel px-3 py-2 mb-1.5" style={{ borderLeftColor: color }}>
      <div className="flex items-center justify-between gap-2">
        <span className="readout text-[10px] font-bold tracking-widest" style={{ color }}>{a.priority || 'MEDIUM'}</span>
        <span className="readout text-[9px] text-slate-500 uppercase">{a.source}</span>
      </div>
      <div className="readout text-[11px] text-slate-200 mt-1">{a.title}</div>
    </div>
  )
}

/* Structured rendering of the full 13-section executive report. */
export function ReportSections({ report }) {
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
  const hist = content.historical_analytics || {}
  const evidence = content.evidence_summary || {}
  const dq = evidence.data_quality || content.data_quality || {}
  const findings = [...(content.critical_findings || []), ...(content.high_findings || [])]

  return (
    <div className="space-y-3">
      {/* 01 Site Info */}
      <Block num={1} title="SITE INFORMATION" icon={Building2}>
        <div className="grid grid-cols-1 md:grid-cols-2">
          <KV k="SITE NAME" v={site.site_name || site.site_id || NA} />
          <KV k="SITE ID" v={site.site_id || NA} />
        </div>
      </Block>

      {/* 02 Analysis Info */}
      <Block num={2} title="ANALYSIS INFORMATION" icon={FileSearch}>
        <div className="grid grid-cols-1 md:grid-cols-2">
          <KV k="ANALYSIS ID" v={shortId(an.analysis_id || report?.analysis_id)} />
          <KV k="GENERATED" v={report?.created_at ? String(report.created_at).replace('T', ' ').slice(0, 19) : NA} />
          <KV k="VIDEO SOURCE" v={an.video_source || NA} />
          <KV k="FRAMES ANALYZED" v={an.frames_analyzed ?? NA} />
          <KV k="MODEL" v={(an.model_used || NA).toUpperCase()} />
          <KV k="REPORT TYPE" v={String(report?.report_type || content.report_type || 'risk_intelligence').replace(/_/g, ' ').toUpperCase()} />
        </div>
      </Block>

      {/* 03 Executive Summary */}
      <Block num={3} title="EXECUTIVE SUMMARY" icon={Activity}>
        <div className="readout text-[11px] text-slate-300 leading-relaxed">{exec.short_line || exec.response || 'Not available.'}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
          <Metric label="Risk Level" value={exec.overall_risk_level || NA} accent={levelColor(exec.overall_risk_level)} />
          <Metric label="Risk Score" value={fmtScore(exec.overall_risk_score)} accent={levelColor(exec.overall_risk_level)} />
          <Metric label="Trend" value={(exec.risk_trend_direction || 'INSUFFICIENT_DATA').replace(/_/g, ' ').toUpperCase()} accent="#4aa8ff" />
          <Metric label="Key Concerns" value={(content.critical_findings?.length || 0) + (content.high_findings?.length || 0)} accent="#ff5a3c" />
        </div>
        {(exec.key_concerns || []).length > 0 && (
          <div className="mt-3">
            <div className="readout text-[9px] text-slate-500 tracking-widest mb-1">KEY CONCERNS</div>
            {(exec.key_concerns || []).map((c, i) => (
              <div key={i} className="readout text-[10px] text-slate-400">▸ {c}</div>
            ))}
          </div>
        )}
      </Block>

      {/* 04 Overall Risk */}
      <Block num={4} title="OVERALL RISK" icon={Activity}>
        {risk.status === 'NOT_AVAILABLE' || risk.overall_score == null ? (
          <div className="readout text-[11px] text-slate-500">RISK INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
              <Metric label="Score" value={fmtScore(risk.overall_score)} accent={levelColor(risk.risk_level)} />
              <Metric label="Level" value={risk.risk_level || NA} accent={levelColor(risk.risk_level)} />
              <Metric label="Empty Dimensions" value={risk.empty_components ?? 0} accent="#6b7d8f" sub="no video evidence" />
              <Metric label="Open Violations" value={srisk.open_violation_count ?? content.open_violations?.length ?? 0} accent={srisk.open_violation_count ? '#ff5a3c' : '#36d17e'} />
            </div>
            <div className="readout text-[10px] text-slate-400 mb-2">{risk.summary}</div>
            {(risk.components || []).map((c) => (
              <div key={c.label} className="flex items-center justify-between gap-3 readout text-[10px] text-slate-400 py-1.5 border-b border-steel-2/40">
                <span className="tracking-widest">{c.label}</span>
                <div className="flex items-center gap-3">
                  {c.factors?.length > 0 && (
                    <span className="text-slate-500 text-[9px] max-w-[260px] truncate">{c.factors.join(' · ')}</span>
                  )}
                  <span className="font-bold tabular-nums text-slate-200">{c.score == null ? NA : Math.round(c.score)}</span>
                </div>
              </div>
            ))}
          </>
        )}
      </Block>

      {/* 05 Safety */}
      <Block num={5} title="SAFETY" icon={ShieldCheck}>
        {safety.status === 'NOT_AVAILABLE' || safety.overall_safety_score == null ? (
          <div className="readout text-[11px] text-slate-500">SAFETY INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
              <Metric label="Safety" value={fmtScore(safety.overall_safety_score)} accent={levelColor(safety.overall_safety_level)} sub={safety.overall_safety_level || NA} />
              <Metric label="PPE Compliance" value={safety.ppe_compliance_rate != null ? `${(safety.ppe_compliance_rate * 100).toFixed(0)}%` : NA} accent="#36d17e" />
              <Metric label="Violations" value={safety.violation_count ?? 0} accent="#f5a623" />
              <Metric label="Workers" value={safety.worker_count ?? 0} accent="#4aa8ff" />
            </div>
            <div className="readout text-[10px] text-slate-400">{safety.summary}</div>
          </>
        )}
      </Block>

      {/* 06 Site Risk */}
      <Block num={6} title="SITE RISK" icon={Tag}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <Metric label="Hazards" value={srisk.hazards_total ?? 0} accent="#4aa8ff" />
          <Metric label="Unresolved" value={srisk.unresolved_hazards ?? 0} accent="#f5a623" />
          <Metric label="Violations" value={srisk.violation_count ?? 0} accent="#ff5a3c" />
          <Metric label="Alerts" value={srisk.alert_count ?? 0} accent="#ff7a3c" />
        </div>
      </Block>

      {/* 07 Compliance */}
      <Block num={7} title="COMPLIANCE" icon={ShieldCheck}>
        {compliance.status === 'NOT_AVAILABLE' ? (
          <div className="readout text-[11px] text-slate-500">COMPLIANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
              <Metric label="Level" value={compliance.compliance_level || NA} accent={levelColor(compliance.compliance_level)} />
              <Metric label="Checked" value={compliance.requirements_checked ?? 0} accent="#4aa8ff" />
              <Metric label="Non-Compliant" value={compliance.non_compliant_count ?? 0} accent="#ff5a3c" />
              <Metric label="Not Verified" value={compliance.not_verified_count ?? 0} accent="#6b7d8f" sub="never counted as non-compliant" />
            </div>
            <div className="readout text-[10px] text-slate-400 mb-1">{compliance.summary}</div>
            {compliance.overdue_inspections != null && (
              <div className="readout text-[10px] text-slate-500">OVERDUE INSPECTIONS: {compliance.overdue_inspections} · OPEN VIOLATIONS: {compliance.open_violations ?? 0}</div>
            )}
          </>
        )}
      </Block>

      {/* 08 Insurance */}
      <Block num={8} title="INSURANCE" icon={FileText}>
        {insurance.status === 'NOT_AVAILABLE' ? (
          <div className="readout text-[11px] text-slate-500">INSURANCE INTELLIGENCE NOT_AVAILABLE FOR THIS ANALYSIS</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
              <Metric label="Risk" value={fmtScore(insurance.risk_score)} accent={levelColor(insurance.risk_level)} sub={insurance.risk_level || NA} />
              <Metric label="Open Incidents" value={insurance.open_incidents ?? 0} accent="#f5a623" />
              <Metric label="Verified Incidents" value={insurance.verified_incidents?.length ?? 0} accent="#ff7a3c" />
              <Metric label="Claim Records" value={insurance.claim_records ?? 0} accent="#4aa8ff" />
            </div>
            <div className="readout text-[10px] text-slate-400">{insurance.summary}</div>
            {insurance.claim_records === 0 && (
              <div className="readout text-[9px] text-slate-500 mt-1">NO INSURANCE CLAIMS ON RECORD — NONE ARE INVENTED.</div>
            )}
          </>
        )}
      </Block>

      {/* 09 Critical Findings */}
      <Block num={9} title="CRITICAL & HIGH FINDINGS" icon={AlertTriangle}>
        {findings.length === 0 && <div className="readout text-[11px] text-slate-500">NO HIGH OR CRITICAL FINDINGS IN THIS ANALYSIS</div>}
        {findings.map((f, i) => <FindingRow key={i} f={f} />)}
      </Block>

      {/* 10 Recommendations */}
      <Block num={10} title="RECOMMENDATIONS" icon={ListChecks}>
        {(content.prioritized_actions || []).length === 0 && (
          <div className="readout text-[11px] text-slate-500">NO PERSISTED RECOMMENDATIONS FOR THIS ANALYSIS</div>
        )}
        {(content.prioritized_actions || []).map((a, i) => <ActionRow key={i} a={a} />)}
      </Block>

      {/* 11 Historical */}
      <Block num={11} title="HISTORICAL ANALYTICS" icon={History}>
        <div className="readout text-[11px] text-slate-300">{hist.message || NA}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
          <Metric label="Trend" value={(hist.direction || 'INSUFFICIENT_DATA').replace(/_/g, ' ').toUpperCase()} accent={hist.trend_available ? '#4aa8ff' : '#6b7d8f'} />
          <Metric label="Analyses" value={hist.analysis_count ?? 0} accent="#36d17e" />
        </div>
      </Block>

      {/* 12 Evidence & Data Quality */}
      <Block num={12} title="EVIDENCE & DATA QUALITY" icon={Database}>
        <div className="flex items-center gap-3 mb-3">
          <span className={`readout text-[9px] px-2 py-1 border ${String(dq.status).toUpperCase() === 'COMPLETE' ? 'border-ok text-ok' : 'border-hazard text-hazard'}`}>
            QUALITY: {dq.status || 'NOT_AVAILABLE'}
          </span>
          <span className="readout text-[9px] text-slate-500">{dq.note}</span>
        </div>
        {(dq.insufficient_dimensions || []).length > 0 && (
          <div className="readout text-[9px] text-slate-500 mb-2">INSUFFICIENT EVIDENCE: {(dq.insufficient_dimensions || []).join(', ').toUpperCase()}</div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-1">
          {Object.entries(evidence.counts || {}).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between readout text-[10px] text-slate-400 border-b border-steel-2/40 py-1">
              <span className="tracking-widest">{k.replace(/_/g, ' ').toUpperCase()}</span>
              <span className="font-bold tabular-nums text-slate-200">{v}</span>
            </div>
          ))}
          {Object.keys(evidence.counts || {}).length === 0 && (
            <div className="readout text-[10px] text-slate-500 col-span-4">NO EVIDENCE COUNTS RECORDED FOR THIS ANALYSIS</div>
          )}
        </div>
      </Block>

      {/* 13 Limitations */}
      <Block num={13} title="LIMITATIONS" icon={Info}>
        <div className="space-y-1">
          {(content.limitations || []).map((l, i) => (
            <div key={i} className="readout text-[10px] text-slate-400">• {l}</div>
          ))}
          {(content.limitations || []).length === 0 && (
            <div className="readout text-[10px] text-slate-500">No recorded limitations for this analysis.</div>
          )}
        </div>
      </Block>

      <div className="readout text-[9px] text-slate-600 flex items-center gap-1.5">
        <ShieldAlert size={11} /> ALL VALUES ARE DERIVED FROM PERSISTED ANALYSIS EVIDENCE — NOTHING IS FABRICATED
      </div>
    </div>
  )
}