import { useId, useState } from 'react'
import { ChevronDown, ChevronRight, ArrowDown } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export const SEV = {
  LOW: '#36d17e',
  MEDIUM: '#f5a623',
  HIGH: '#ff7a3c',
  CRITICAL: '#ff5a3c',
}

const NEUTRAL = '#6b7d8f'

export const sevColor = (l) => SEV[String(l || '').toUpperCase()] || NEUTRAL

const clamp = (v) => Math.min(Math.max(Number(v) || 0, 0), 100)

/** Circular gauge — pure SVG, gloss-free, used for scores / progress. */
export function Gauge({ value, color, label, sub, size = 88 }) {
  const gid = useId().replace(/:/g, '')
  const ok = value != null && !Number.isNaN(value)
  const v = clamp(ok ? value : 0)
  const c = color || sevColor(label)
  const R = 42
  const C = 2 * Math.PI * R
  const filled = (v / 100) * C
  return (
    <div className="relative mx-auto" style={{ width: size, height: size }}>
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <defs>
          <filter id={gid}><feGaussianBlur stdDeviation="2" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <circle cx="60" cy="60" r={R} fill="none" stroke="#1c2530" strokeWidth="8" />
        <circle cx="60" cy="60" r={R} fill="none" stroke={ok ? c : '#2a3542'} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={`${filled} ${C}`}
          strokeDashoffset={ok ? 0 : C * 0.25}
          style={ok ? { filter: `url(#${gid})` } : undefined} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {ok ? (
          <>
            <div className="readout font-black text-white tabular-nums" style={{ fontSize: size * 0.24 }}>{Math.round(v)}</div>
            {sub && <div className="readout text-[8px] tracking-[0.2em] mt-0.5" style={{ color: c }}>{sub}</div>}
          </>
        ) : (
          <div className="readout text-[11px] text-slate-600 tracking-widest">N/A</div>
        )}
      </div>
    </div>
  )
}

/** Donut chart from real category slices. */
export function Donut({ slices, centerAdult, center }) {
  const total = (slices || []).reduce((a, s) => a + Math.max(s.value || 0, 0), 0)
  const R = 38
  const C = 2 * Math.PI * R
  let acc = 0
  const arcs = (slices || []).map((s) => {
    const frac = total ? (Number(s.value) || 0) / total : 0
    const arc = { ...s, dash: `${frac * C} ${C}`, offset: -(acc / total) * C }
    acc += Number(s.value) || 0
    return arc
  })
  return (
    <div className="flex items-center gap-4">
      <div className="relative" style={{ width: 110, height: 110 }}>
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r={R} fill="none" stroke="#1c2530" strokeWidth="13" />
          {arcs.map((a, i) => (
            <circle key={i} cx="60" cy="60" r={R} fill="none" stroke={a.color || '#2a3542'}
              strokeWidth="13" strokeLinecap="butt"
              strokeDasharray={a.dash} strokeDashoffset={a.offset} />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="readout text-xl font-black text-white tabular-nums">{center != null ? center : total}</div>
          {centerAdult && <div className="readout text-[8px] text-slate-500 tracking-widest mt-0.5">{centerAdult.toUpperCase()}</div>}
        </div>
      </div>
      <div className="space-y-1.5 min-w-0">
        {arcs.map((a, i) => (
          <div key={i} className="flex items-center justify-between gap-3 readout text-[10px]">
            <span className="flex items-center gap-1.5 tracking-widest text-slate-400">
              <span className="w-2 h-2 rounded-[2px]" style={{ background: a.color || '#2a3542' }} />
              {a.label}
            </span>
            <span className="font-bold tabular-nums text-slate-200">{a.value}</span>
          </div>
        ))}
        {total === 0 && <div className="readout text-[10px] text-slate-500">NO DATA</div>}
      </div>
    </div>
  )
}

/** Compact horizontal bar chart. items: [{ label, value, color }] */
export function Bars({ items, max: forcedMax }) {
  const values = (items || []).map((i) => Number(i.value) || 0)
  const max = forcedMax != null && forcedMax > 0 ? forcedMax : Math.max(1, ...values)
  if (!items?.length) return <div className="readout text-[10px] text-slate-500">NO DATA</div>
  return (
    <div className="space-y-2">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="readout text-[9px] tracking-widest text-slate-400 w-28 shrink-0 truncate text-right">{it.label}</span>
          <div className="flex-1 h-2.5 bg-[#0a0e13] border border-steel rounded-[2px] overflow-hidden">
            <div className="h-full transition-all"
              style={{ width: `${clamp((Number(it.value) || 0) / max * 100)}%`, background: it.color || '#4aa8ff' }} />
          </div>
          <span className="readout text-[11px] font-bold tabular-nums w-9 text-right" style={{ color: it.color || 'var(--color-ink)' }}>
            {Number(it.value) || 0}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Line/area trend from real point data: [{ label, value }]. Guarded by caller. */
export function TrendChart({ data, color = '#f5a623', height = 200 }) {
  if (!data || data.length < 2) return null
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1c2530" vertical={false} />
        <XAxis dataKey="label" stroke="#6b7d8f" fontSize={9} tickLine={false} minTickGap={18} />
        <YAxis domain={[0, 100]} stroke="#6b7d8f" fontSize={9} tickLine={false} />
        <Tooltip
          contentStyle={{ backgroundColor: '#0f141a', border: '1px solid #2a3542', fontFamily: 'monospace', color: '#e5e7eb', fontSize: 11 }}
          labelStyle={{ color: '#e5e7eb' }}
        />
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2.5}
          fill="url(#trendFill)" dot={{ r: 2.5, fill: color, strokeWidth: 0 }} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/** Empty-state helper. */
export function EmptyState({ icon: Icon, msg, compact = true }) {
  return (
    <div className={`flex items-center justify-center gap-2 ${compact ? 'py-4' : 'py-10 text-center'} readout text-[11px] text-slate-500`}>
      {Icon && <Icon size={14} className="text-slate-600 shrink-0" />}
      <span>{msg}</span>
    </div>
  )
}

/** Collapsible card — the app's progressive-disclosure idiom. */
export function ExpandCard({ title, badge, icon: Icon, accent = 'text-info', open, onToggle, children, defaultOpen = false }) {
  const [openInt, setOpenInt] = useState(defaultOpen)
  const isOpen = onToggle ? !!open : openInt
  const toggle = onToggle || (() => setOpenInt(!openInt))
  return (
    <div className="tech-panel overflow-hidden">
      <button onClick={toggle}
        className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left">
        <span className="bracket-label flex items-center gap-2">
          {Icon && <Icon size={13} className={accent} />} {title}
          {badge != null && badge !== '' && (
            <span className="readout text-[9px] text-slate-500 tracking-widest">· {badge}</span>
          )}
        </span>
        {isOpen ? <ChevronDown size={13} className="text-hazard shrink-0" /> : <ChevronRight size={13} className="text-slate-500 shrink-0" />}
      </button>
      {isOpen && <div className="px-4 pb-4 border-t border-steel/60 pt-3">{children}</div>}
    </div>
  )
}

/** Visual pipeline flowchart. steps: [{ icon: Icon, label, sub }] */
export function PipelineFlow({ steps }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-5">
      {steps.map((s, i) => (
        <div key={i} className="relative flex items-start gap-2">
          <div className="flex flex-col items-center">
            <span className="readout text-[8px] text-slate-600 tracking-widest mb-0.5">{String(i + 1).padStart(2, '0')}</span>
            <div className="w-10 h-10 rounded-[4px] bg-panel-3 border border-steel-2 flex items-center justify-center"
              style={{ color: s.color || '#4aa8ff' }}>
              <s.icon size={17} />
            </div>
            {i < steps.length - 1 && (
              <ArrowDown size={13} className="text-slate-600 my-0.5" />
            )}
          </div>
          <div className="min-w-0 pt-3">
            <div className="readout text-[10px] font-bold text-slate-200 tracking-wide leading-tight">{s.label}</div>
            {s.sub && <div className="readout text-[8px] text-slate-500 mt-0.5 leading-tight">{s.sub}</div>}
          </div>
        </div>
      ))}
    </div>
  )
}