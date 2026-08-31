import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Activity, RefreshCw } from 'lucide-react'

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
  const [risk, setRisk] = useState(null)
  const [history, setHistory] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [r, h, rec] = await Promise.all([
        api.getCurrentRisk(siteId),
        api.getRiskHistory(siteId),
        api.getRecommendations(siteId),
      ])
      setRisk(r.data); setHistory(h.data); setRecommendations(rec.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.getRiskAnalysis(siteId); await load() } finally { setRunning(false) }
  }

  if (loading && !risk) return <div className="p-8 readout text-slate-400 text-center">LOADING RISK ANALYSIS...</div>

  const level = risk?.risk_level || 'LOW'
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
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">EXPLAINABLE SCORING · WHY THIS SCORE · DECISION CONSOLE</div>
        </div>
        <button onClick={runAnalysis} disabled={running}
          className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          <RefreshCw size={13} className={running ? 'animate-spin' : ''} /> {running ? 'ANALYZING...' : 'REFRESH ANALYSIS'}
        </button>
      </div>

      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Overall assessment */}
        <div className="tech-panel p-5">
          <div className="bracket-label mb-3 flex items-center gap-1.5"><Activity size={12} /> CURRENT ASSESSMENT</div>
          <div className="text-6xl font-black text-white tabular-nums">{risk?.overall_score.toFixed(0)}</div>
          <div className="readout text-lg font-bold mt-1" style={{ color }}>{level}</div>
          <div className="mt-4 space-y-2">
            {COMPONENTS.map(({ key, label, hex }) => (
              <div key={key} className="flex items-center justify-between readout text-[10px] text-slate-400">
                <span className="flex items-center gap-2 tracking-widest"><span className="w-1.5 h-1.5" style={{ background: hex }} />{label}</span>
                <span className="text-slate-200 font-bold tabular-nums">{risk?.[`${key}_score`] !== undefined ? Math.round(risk[`${key}_score`]) : '—'}</span>
              </div>
            ))}
          </div>
          <p className="text-[11px] readout text-slate-400 mt-4 border-t border-steel pt-3 leading-relaxed">{risk?.summary}</p>
          <div className="readout text-[10px] text-slate-600 mt-2">{risk?.timestamp ? formatTime(risk.timestamp) : ''}</div>
        </div>

        {/* Trend chart */}
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="bracket-label mb-2">RISK TREND · ROLLING HISTORY</div>
          {chartData.length > 1 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1c2530" />
                <XAxis dataKey="time" stroke="#5b6b7c" fontSize={10} tickLine={false} />
                <YAxis domain={[0, 100]} stroke="#5b6b7c" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0a0e13', border: '1px solid #f5a623', fontFamily: 'monospace' }}
                  labelStyle={{ color: '#e5e7eb' }}
                />
                <Line type="monotone" dataKey="score" stroke="#f5a623" strokeWidth={3} dot={{ r: 3, fill: '#f5a623' }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="readout text-slate-500 text-center py-16 text-sm">COLLECT MORE ASSESSMENTS TO BUILD TREND — CLICK "REFRESH ANALYSIS"</div>
          )}
        </div>
      </div>

      {/* Contributors + recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-7 gap-3">
        <div className="lg:col-span-4 space-y-3">
          <div className="bracket-label">RISK CONTRIBUTORS · FACTOR ANALYSIS</div>
          {COMPONENTS.map(({ key, label, hex }) => {
            const factors = risk?.[`${key}_factors`] || []
            const score = risk?.[`${key}_score`] || 0
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
                      <span className="text-slate-600 mt-0.5">›</span> {f}
                    </div>
                  )) : (
                    <div className="readout text-[11px] text-slate-500">NO CONTRIBUTING FACTORS DETECTED</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="lg:col-span-3 tech-panel p-4">
          <div className="bracket-label mb-3">RECOMMENDED ACTIONS</div>
          {recommendations.length === 0 && <div className="readout text-slate-500 text-center py-8 text-sm">NO RECOMMENDATIONS YET</div>}
          {recommendations.map((rec) => {
            const c = LEVEL_HEX[rec.priority] || '#36d17e'
            return (
              <div key={rec.id} className="border border-steel bg-[#0a0e13] p-3 mb-2 border-l-2" style={{ borderLeftColor: c }}>
                <div className="flex items-center justify-between">
                  <span className="readout text-[10px] font-bold tracking-widest" style={{ color: c }}>{rec.priority}</span>
                  <span className="readout text-[9px] text-slate-500 uppercase">{rec.hazard_type.replace(/_/g, ' ')}</span>
                </div>
                <div className="text-[13px] text-white font-semibold mt-1.5 readout">{rec.title}</div>
                <p className="text-[11px] text-slate-400 mt-1 readout">{rec.description}</p>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
