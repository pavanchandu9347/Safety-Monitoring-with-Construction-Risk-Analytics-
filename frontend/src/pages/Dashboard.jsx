import { useDashboard } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import {
  TrendingUp, TrendingDown, Minus, ShieldAlert, Droplets, Wrench, MapPin,
  Activity, Crosshair, Gauge, Radio, RefreshCw
} from 'lucide-react'

const LEVEL_COLOR = {
  LOW: '#36d17e',
  MEDIUM: '#f5a623',
  HIGH: '#ff7a3c',
  CRITICAL: '#ff5a3c',
}

function GaugeSegment({ value, label, color }) {
  const v = Math.min(Math.max(value || 0, 0), 100)
  return (
    <div className="flex-1 tech-panel p-3">
      <div className="bracket-label mb-2 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
        {label}
      </div>
      <div className="flex items-end gap-2">
        <span className="readout text-3xl font-bold text-white tabular-nums">{v.toFixed(0)}</span>
        <span className="readout text-slate-600 text-xs mb-1">/100</span>
      </div>
      <div className="mt-2 h-1.5 bg-[#0a0e13] border border-steel rounded-full overflow-hidden">
        <div className="h-full" style={{ width: `${v}%`, background: color, boxShadow: `0 0 8px ${color}` }} />
      </div>
    </div>
  )
}

function RiskDial({ score, level }) {
  const color = LEVEL_COLOR[level] || '#36d17e'
  const R = 52, C = 2 * Math.PI * R
  const filled = (score / 100) * C
  return (
    <div className="relative w-44 h-44 mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <defs>
          <filter id="glow"><feGaussianBlur stdDeviation="2" result="b" /><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <circle cx="60" cy="60" r={R} fill="none" stroke="#1c2530" strokeWidth="7" />
        <circle cx="60" cy="60" r={R} fill="none" stroke={color} strokeWidth="7"
          strokeLinecap="round" strokeDasharray={`${filled} ${C}`} filter="url(#glow)" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="readout text-5xl font-black text-white tabular-nums">{score.toFixed(0)}</div>
        <div className="readout text-xs font-bold tracking-[0.2em] mt-1" style={{ color }}>{level}</div>
        <div className="text-[9px] text-slate-500 readout tracking-widest mt-0.5">SITE RISK SCORE</div>
      </div>
    </div>
  )
}

function TrendBadge({ trend }) {
  if (!trend || trend.length < 2) return <span className="readout text-slate-500 text-xs">NO HISTORY</span>
  const first = trend[0].score, last = trend[trend.length - 1].score
  const diff = last - first
  const dir = diff > 2 ? 'up' : diff < -2 ? 'down' : 'stable'
  const cfg = {
    up: { Icon: TrendingUp, c: '#ff5a3c', t: 'RISING' },
    down: { Icon: TrendingDown, c: '#36d17e', t: 'FALLING' },
    stable: { Icon: Minus, c: '#f5a623', t: 'STABLE' },
  }[dir]
  return (
    <div className="flex items-center gap-2">
      <cfg.Icon size={15} style={{ color: cfg.c }} />
      <span className="readout text-[11px] font-bold" style={{ color: cfg.c }}>{cfg.t}</span>
      <span className="readout text-slate-500 text-[10px]">Δ {(diff > 0 ? '+' : '')}{diff.toFixed(1)}</span>
    </div>
  )
}

function ZoneTile({ zone, selected, onSelect }) {
  const color = LEVEL_COLOR[zone.risk_level] || '#36d17e'
  const meta = {
    'excavation': { ann: 'EXC-1', name: 'EXCAVATION' },
    'storage': { ann: 'STO-2', name: 'MATERIAL STORE' },
    'structural': { ann: 'STR-3', name: 'BUILDING CORE' },
  }[zone.zone_type] || { ann: 'GEN', name: zone.zone_type }
  return (
    <button onClick={onSelect}
      className={`tech-panel text-left p-3 transition ${selected ? '!border-hazard' : 'hover:!border-steel-2'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="readout text-[9px] text-slate-500 tracking-widest">{meta.ann}</span>
        <span className="led led-on" style={{ background: color, color }} />
      </div>
      <div className="readout text-[11px] font-bold text-white tracking-wide">{meta.name}</div>
      <div className="text-[10px] text-slate-500">{zone.zone_name}</div>
      <div className="mt-3 flex items-end justify-between border-t border-steel pt-2">
        <span className="readout text-2xl font-bold tabular-nums" style={{ color }}>{zone.risk_score.toFixed(0)}</span>
        <div className="text-right">
          <div className="readout text-[9px] text-slate-500">{zone.risk_level}</div>
          <div className="readout text-[9px] text-slate-500">{zone.active_hazard_count} HAZ</div>
        </div>
      </div>
    </button>
  )
}

export default function Dashboard() {
  const siteId = useSite()
  const { data, error, reload } = useDashboard(8000)
  const [selectedZone, setSelectedZone] = useState(null)
  const [generating, setGenerating] = useState(false)

  if (error && !data) {
    return (
      <div className="p-6">
        <div className="tech-panel p-5 border-l-signal">
          <p className="readout text-signal font-bold">⚠ SYS OFFLINE — {error}</p>
          <p className="readout text-slate-400 text-xs mt-2">Ensure backend is running on port 8001.</p>
        </div>
      </div>
    )
  }
  if (!data) {
    return <div className="p-6 readout text-slate-500">BOOTING SITE RISK MONITORING...</div>
  }

  const risk = data.current_risk_assessment
  const level = risk?.risk_level || 'LOW'
  const color = LEVEL_COLOR[level]

  const handleGenerate = async () => {
    setGenerating(true)
    try { await api.generateDemo(siteId); await reload() } finally { setGenerating(false) }
  }

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* ── Command bar ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Crosshair className="text-hazard" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">RIVERSIDE TOWER — SITE A1</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">CONSTRUCTION RISK OPERATIONS CENTER · MILESTONE 1</div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating}
            className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            {generating ? '│ . . . ' : ''}
            {generating ? 'RE-RUNNING ANALYSIS' : <><RefreshCw size={13} /> RUN RISK ANALYSIS</>}
          </button>
        </div>
      </div>

      {/* ── Hazard strip indicator ── */}
      <div className="flex items-center gap-2">
        <div className="hazard-bar h-4 w-24"></div>
        <div className="readout text-[10px] text-slate-400 tracking-widest">ACTIVE WARNING TAPE · SITE STATUS: <span style={{ color }} className="font-bold">{level}</span></div>
      </div>

      {/* ── Main instrumentation row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        {/* Risk dial */}
        <div className="tech-panel p-4 lg:col-span-2 flex flex-col items-center justify-center">
          <div className="bracket-label self-start mb-1 flex items-center gap-1.5"><Gauge size={12} /> PRIMARY RISK GAUGE</div>
          <RiskDial score={risk?.overall_score || 0} level={level} />
          <div className="mt-3 w-full border-t border-steel pt-2 flex items-center justify-between">
            <span className="bracket-label">TREND</span>
            <TrendBadge trend={data?.risk_trend} />
          </div>
        </div>

        {/* Component gauges */}
        <div className="lg:col-span-3 grid grid-cols-2 gap-3">
          <GaugeSegment label="ENVIRONMENTAL" value={risk?.environmental_score} color="#4aa8ff" />
          <GaugeSegment label="EQUIPMENT" value={risk?.equipment_score} color="#f5a623" />
          <GaugeSegment label="SITE CONDITION" value={risk?.site_condition_score} color="#36d17e" />
          <GaugeSegment label="ACTIVITY" value={risk?.activity_score} color="#b794ff" />
        </div>
      </div>

      {/* ── Site map + key stats ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Virtual site map */}
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="bracket-label flex items-center gap-1.5"><Radio size={12} /> VIRTUAL SITE LAYOUT · ZONE MATRIX</span>
            <div className="flex gap-3 readout text-[9px] text-slate-500">
              {Object.entries(LEVEL_COLOR).map(([k, c]) => (
                <span key={k} className="flex items-center gap-1"><span className="led" style={{ background: c }} />{k}</span>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {data.zone_risk_data?.map((z) => (
              <ZoneTile key={z.zone_id} zone={z}
                selected={selectedZone === z.zone_id}
                onSelect={() => setSelectedZone(selectedZone === z.zone_id ? null : z.zone_id)} />
            ))}
          </div>

          {selectedZone && (() => {
            const z = data.zone_risk_data.find((x) => x.zone_id === selectedZone)
            return z ? (
              <div className="mt-3 border border-hazard/40 bg-hazard/5 p-3 readout text-[11px] text-slate-300">
                <span className="text-hazard font-bold tracking-widest">ZONE {z.zone_name.toUpperCase()}</span>
                <span className="text-slate-500"> — RISK {z.risk_level} · SCORE {z.risk_score.toFixed(0)} · HAZARDS {z.active_hazard_count} · EVENTS {z.event_count}</span>
                <span className="text-slate-500"> // VIEW DETAILS IN RISK ANALYSIS</span>
              </div>
            ) : null
          })()}
        </div>

        {/* Key stats stack */}
        <div className="space-y-3">
          <div className="tech-panel p-3 grid grid-cols-2 gap-3">
            {[
              { l: 'OPEN HAZARDS', v: data.open_hazards, c: '#ff7a3c', i: ShieldAlert },
              { l: 'CRITICAL', v: data.critical_hazards, c: '#ff5a3c', i: Activity },
              { l: 'EQUIPMENT', v: data.equipment?.length, c: '#4aa8ff', i: Wrench },
              { l: 'RECOMMEND', v: data.total_recommendations, c: '#36d17e', i: MapPin },
            ].map(({ l, v, c, i: Icon }) => (
              <div key={l} className="bg-[#0a0e13] border border-steel p-2.5">
                <div className="flex items-center gap-1.5 readout text-[9px] text-slate-500 tracking-widest"><Icon size={12} style={{ color: c }} />{l}</div>
                <div className="readout text-2xl font-bold tabular-nums" style={{ color: c }}>{v}</div>
              </div>
            ))}
          </div>

          <div className="tech-panel p-3">
            <div className="bracket-label mb-2">HAZARD ENGINE — ACTIVE</div>
            {data.active_hazards?.slice(0, 4).map((h) => {
              const cc = LEVEL_COLOR[h.severity] || '#36d17e'
              return (
                <div key={h.id} className="flex items-center justify-between py-1.5 border-b border-steel/50 last:border-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="led" style={{ background: cc }} />
                    <span className="readout text-[11px] text-slate-300 truncate capitalize">{h.hazard_type.replace(/_/g, ' ')}</span>
                  </div>
                  <span className="readout text-[9px] text-slate-500">{formatTime(h.timestamp)}</span>
                </div>
              )
            })}
            {data.active_hazards?.length === 0 && <div className="readout text-[11px] text-slate-500">NO ACTIVE HAZARDS</div>}
          </div>
        </div>
      </div>

      {/* ── Equipment + environmental readout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="bracket-label mb-2">EQUIPMENT TELEMETRY <span className="text-slate-600">· SIMULATED</span></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {data.equipment?.map((eq) => (
              <div key={eq.id} className="flex items-center justify-between bg-[#0a0e13] border border-steel px-3 py-2">
                <div className="readout">
                  <div className="text-[12px] text-slate-200 font-semibold">{eq.name}</div>
                  <div className="text-[9px] text-slate-500 tracking-wider uppercase">{eq.activity}{eq.nearby_worker_count > 0 ? ` · ${eq.nearby_worker_count} wrk` : ''}</div>
                </div>
                <span className="readout text-[10px] px-1.5 py-0.5 font-semibold"
                  style={eq.status === 'active' ? { color: '#36d17e', border: '1px solid #36d17e' }
                    : eq.status === 'maintenance' ? { color: '#f5a623', border: '1px solid #f5a623' }
                    : { color: '#7e8c9c', border: '1px solid #2a3542' }}>{eq.status.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="tech-panel p-4">
          <div className="bracket-label mb-2 flex items-center gap-1.5"><Droplets size={12} /> SUMMARY</div>
          <p className="readout text-[11px] text-slate-300 leading-relaxed">{risk?.summary || 'Awaiting risk assessment...'}</p>
        </div>
      </div>
    </div>
  )
}
