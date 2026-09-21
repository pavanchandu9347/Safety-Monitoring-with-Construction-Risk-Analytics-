import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Activity, RefreshCw, ToyBrick, Lightbulb, ShieldAlert, TrendingUp, Loader2, Video, ScanLine, ListChecks, Umbrella, BrainCircuit, FileText, Boxes } from 'lucide-react'
import { StatChip, Section, ActionBar } from '../components/progressive'
import { PipelineFlow } from '../components/visuals'

const PIPELINE_STEPS = [
  { icon: Video, label: 'VIDEO INPUT', sub: 'site footage', color: '#4aa8ff' },
  { icon: ScanLine, label: 'COMPUTER VISION', sub: 'YOLO sampling', color: '#4aa8ff' },
  { icon: ShieldAlert, label: 'SAFETY AGENT', sub: 'PPE · violations', color: '#f5a623' },
  { icon: Activity, label: 'SITE RISK ENGINE', sub: '0-100 scoring', color: '#ff7a3c' },
  { icon: ListChecks, label: 'COMPLIANCE AGENT', sub: 'regulatory checks', color: '#36d17e' },
  { icon: Umbrella, label: 'INSURANCE AGENT', sub: 'exposure · claims', color: '#ff7a3c' },
  { icon: BrainCircuit, label: 'RISK INTELLIGENCE', sub: 'unified context', color: '#b794ff' },
  { icon: FileText, label: 'REPORT AGENT', sub: 'reports · alerts', color: '#36d17e' },
]

const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const COMPONENTS = [
  { key: 'environmental', label: 'ENVIRONMENTAL', hex: '#4aa8ff' },
  { key: 'equipment', label: 'EQUIPMENT', hex: '#f5a623' },
  { key: 'site_condition', label: 'SITE CONDITION', hex: '#36d17e' },
  { key: 'activity', label: 'ACTIVITY', hex: '#b794ff' },
]

export default function Analysis() {
  const siteId = useSite()
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [detail, setDetail] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const [l, h, rec] = await Promise.all([
        api.getLatestRiskAnalysis(siteId),
        api.getRiskHistory(siteId),
        api.getRecommendations(siteId),
      ])
      setLatest(l.data?.status === 'completed' ? l.data : null)
      setHistory(h.data); setRecommendations(rec.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.analyzeVideo(siteId); await load() } finally { setRunning(false) }
  }

  if (loading && !latest) return <div className="p-8 readout text-slate-400 text-center">LOADING RISK ANALYSIS...</div>

  const risk = latest?.risk || {}
  const level = risk.risk_level || 'LOW'
  const color = LEVEL_HEX[level] || '#36d17e'

  const chartData = history.map((h) => ({ time: formatTime(h.timestamp), score: Math.round(h.score), level: h.risk_level }))

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="text-info" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">RISK ANALYSIS</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">VIDEO-DERIVED · EXPLAINABLE SCORING · DECISION CONSOLE</div>
        </div>
        <button onClick={runAnalysis} disabled={running}
          className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          {running ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} {running ? 'ANALYZING VIDEO...' : 'RE-ANALYZE SITE VIDEO'}
        </button>
      </div>

      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      {/* ── Analysis pipeline flowchart ── */}
      <div className="tech-panel p-4">
        <div className="bracket-label mb-3 flex items-center gap-1.5">
          <Boxes size={12} className="text-info" /> CONTEXT-AWARE ANALYSIS PIPELINE · ONE VIDEO → ONE REPORT
        </div>
        <PipelineFlow steps={PIPELINE_STEPS} />
        <div className="readout text-[9px] text-slate-600 mt-3 border-t border-steel pt-2">
          EVERY CELL WRITES TO THE SAME ANALYSIS RECORD — SAFETY · RISK · COMPLIANCE · INSURANCE FINDINGS STAY TRACEABLE TO ONE analysis_id.
        </div>
      </div>

      {!latest && (
        <div className="tech-panel p-6 text-center readout text-slate-500">
          <div className="text-[13px]">NO VIDEO ANALYSIS YET</div>
          <div className="text-[10px] mt-1 text-slate-400">RUN "ANALYZE SITE VIDEO" ON THE DASHBOARD OR THE COMPUTER VISION BAY — ONE ANALYSIS SHARED BY ALL CONSOLES</div>
        </div>
      )}

      {latest && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            {/* Overall assessment */}
            <div className="tech-panel p-5">
              <div className="bracket-label mb-3 flex items-center gap-1.5"><Activity size={12} /> CURRENT ASSESSMENT</div>
              <div className="text-6xl font-black text-white tabular-nums">{risk.overall_score != null ? risk.overall_score.toFixed(0) : '—'}</div>
              <div className="readout text-lg font-bold mt-1" style={{ color }}>{level}</div>
              <div className="mt-4 space-y-2">
                {COMPONENTS.map(({ key, label, hex }) => (
                  <div key={key} className="flex items-center justify-between readout text-[10px] text-slate-400">
                    <span className="flex items-center gap-2 tracking-widest"><span className="w-1.5 h-1.5" style={{ background: hex }} />{label}</span>
                    <span className="text-slate-200 font-bold tabular-nums">{risk[`${key}_score`] != null ? Math.round(risk[`${key}_score`]) : '—'}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] readout text-slate-400 mt-4 border-t border-steel pt-3 leading-relaxed">{risk.summary || 'Awaiting analysis...'}</p>
              <div className="readout text-[10px] text-slate-400 mt-2">
                {latest.timestamp ? formatTime(latest.timestamp) : ''} · {latest.video?.filename || ''}
              </div>
              {latest.evidence_note && (
                <div className="readout text-[9px] text-slate-500 border-l-2 border-steel-2 bg-[#0a0e13] p-2 mt-2 leading-relaxed">{latest.evidence_note}</div>
              )}
            </div>

            {/* Trend chart */}
            <div className="lg:col-span-2 tech-panel p-4">
              <div className="bracket-label mb-2">RISK TREND · ANALYSIS HISTORY</div>
              {chartData.length > 1 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="#1c2530" />
                    <XAxis dataKey="time" stroke="#6b7d8f" fontSize={10} tickLine={false} />
                    <YAxis domain={[0, 100]} stroke="#6b7d8f" fontSize={10} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f141a', border: '1px solid #f5a623', fontFamily: 'monospace', color: '#e5e7eb' }}
                      labelStyle={{ color: '#e5e7eb' }}
                    />
                    <Line type="monotone" dataKey="score" stroke="#f5a623" strokeWidth={3} dot={{ r: 3, fill: '#f5a623' }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="readout text-slate-500 text-center py-16 text-sm">RUN ANALYSIS TWICE OR MORE TO BUILD A TREND</div>
              )}
            </div>
          </div>

          {/* Overview chips */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatChip icon={ShieldAlert} label="Current Score" value={risk.overall_score?.toFixed(0) ?? '—'} accent={color} />
            <StatChip icon={TrendingUp} label="Assessments" value={history.length} accent="#4aa8ff" />
            <StatChip icon={ToyBrick} label="Active Hazards" value={latest.hazards?.length ?? 0} accent="#f5a623" />
            <StatChip icon={Lightbulb} label="Recommendations" value={recommendations.length} accent="#36d17e" />
          </div>

          {/* Action bar */}
          <ActionBar
            active={detail}
            onToggle={(k) => setDetail(detail === k ? null : k)}
            items={[
              { key: 'contributors', label: 'Contributors', icon: ToyBrick },
              { key: 'hazards', label: 'Hazards', icon: ShieldAlert },
              { key: 'recommendations', label: 'Recommendations', icon: Lightbulb },
            ]}
          />

          {detail === 'contributors' && (
            <Section title="RISK CONTRIBUTORS · FACTOR ANALYSIS" badge={`${COMPONENTS.length} DIMENSIONS`} onClose={() => setDetail(null)}>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {COMPONENTS.map(({ key, label, hex }) => {
                  const factors = risk[`${key}_factors`] || []
                  const score = risk[`${key}_score`] || 0
                  return (
                    <div key={key} className="tech-panel p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 readout text-[12px] text-slate-100 font-semibold tracking-wide">
                          <span className="w-2 h-2" style={{ background: hex }} /> {label}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-36 h-2 bg-[#0a0e13] border border-steel overflow-hidden">
                            <div className="h-full" style={{ width: `${score}%`, background: hex }} />
                          </div>
                          <span className="readout text-[12px] font-bold text-white w-8 text-right tabular-nums">{Math.round(score)}</span>
                        </div>
                      </div>
                      <div className="mt-2 space-y-1">
                        {factors.length > 0 ? factors.map((f, i) => (
                          <div key={i} className="readout text-[11px] text-slate-300 flex items-start gap-2">
                            <span className="text-slate-400 mt-0.5">›</span> {f}
                          </div>
                        )) : (
                          <div className="readout text-[11px] text-slate-500">NO CONTRIBUTING FACTORS — VIDEO PROVIDED NO EVIDENCE FOR THIS DIMENSION</div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </Section>
          )}

          {detail === 'hazards' && (
            <Section title="DETECTED HAZARDS" badge={`${latest.hazards?.length || 0} HAZARDS`} onClose={() => setDetail(null)}>
              <div className="max-h-[420px] overflow-y-auto space-y-1">
                {(latest.hazards || []).map((h, i) => {
                  const c = LEVEL_HEX[String(h.severity).toUpperCase()] || '#36d17e'
                  return (
                    <div key={h.id || i} className="flex items-center justify-between border border-steel bg-[#0a0e13] px-3 py-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="led" style={{ background: c }} />
                        <div className="readout min-w-0">
                          <div className="text-[11px] text-slate-200 capitalize truncate">{String(h.hazard_type || '').replace(/_/g, ' ')}</div>
                          {h.description && <div className="text-[9px] text-slate-500 truncate">{h.description}</div>}
                        </div>
                      </div>
                      <span className="readout text-[9px] font-bold px-1.5 py-0.5 shrink-0" style={{ color: c, border: `1px solid ${c}` }}>
                        {(h.severity || 'LOW').toUpperCase()}
                      </span>
                    </div>
                  )
                })}
                {!latest.hazards?.length && <div className="readout text-[11px] text-slate-500">NO HAZARDS DETECTED IN THIS ANALYSIS</div>}
              </div>
            </Section>
          )}

          {detail === 'recommendations' && (
            <Section title="RECOMMENDED ACTIONS" badge={`${latest.recommendations?.length || 0} ACTIONS`} onClose={() => setDetail(null)}>
              {!latest.recommendations?.length && <div className="readout text-slate-500 text-center py-8 text-sm">NO RECOMMENDATIONS YET</div>}
              <div className="max-h-[480px] overflow-y-auto">
                {(latest.recommendations || []).map((rec, i) => {
                  const c = LEVEL_HEX[String(rec.priority).toUpperCase()] || '#36d17e'
                  return (
                    <div key={i} className="border border-steel bg-[#0a0e13] p-3 mb-2 border-l-2" style={{ borderLeftColor: c }}>
                      <div className="flex items-center justify-between">
                        <span className="readout text-[10px] font-bold tracking-widest" style={{ color: c }}>{(rec.priority || '').toUpperCase()}</span>
                        <span className="readout text-[9px] text-slate-500 uppercase">{String(rec.hazard_type || '').replace(/_/g, ' ')}</span>
                      </div>
                      <div className="text-[13px] text-white font-semibold mt-1.5 readout">{rec.title}</div>
                      <p className="text-[11px] text-slate-400 mt-1 readout">{rec.description}</p>
                    </div>
                  )
                })}
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  )
}