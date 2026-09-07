import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, ShieldAlert, Activity, Camera, Radio, HardHat,
  Gauge, Cylinder, Crosshair
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'

const RISK_LEVELS = {
  LOW: { label: 'LOW', color: '#36d17e' },
  MEDIUM: { label: 'MEDIUM', color: '#f5a623' },
  HIGH: { label: 'HIGH', color: '#ff7a3c' },
  CRITICAL: { label: 'CRITICAL', color: '#ff5a3c' },
}

const NAV = [
  { to: '/', label: 'OPS. DASHBOARD', icon: LayoutDashboard, code: '01' },
  { to: '/monitoring', label: 'SENSOR FEED', icon: Radio, code: '02' },
  { to: '/video', label: 'CV / DATASET', icon: Camera, code: '03' },
  { to: '/hazards', label: 'HAZARD LOG', icon: ShieldAlert, code: '04' },
  { to: '/analysis', label: 'RISK ANALYSIS', icon: Activity, code: '05' },
  { to: '/safety', label: 'SAFETY CTL', icon: HardHat, code: '06' },
]

export default function Layout() {
  const siteId = useSite()
  const [risk, setRisk] = useState(null)
  const [clock, setClock] = useState('')
  const location = useLocation()

  useEffect(() => {
    api.getCurrentRisk(siteId).then((r) => setRisk(r.data)).catch(() => {})
  }, [siteId])

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toISOString().slice(11, 19) + ' Z'), 1000)
    return () => clearInterval(t)
  }, [])

  const level = RISK_LEVELS[risk?.risk_level] || RISK_LEVELS.LOW

  return (
    <div className="min-h-screen flex flex-col text-slate-200">
      {/* ── Top machined header bar ── */}
      <header className="border-b border-steel bg-[#0e1218] flex items-stretch">
        {/* Callout block */}
        <div className="flex items-center gap-3 px-4 py-2 border-r border-steel">
          <div className="w-11 h-11 rounded-[4px] bg-[#151a21] border border-steel flex items-center justify-center shadow-inner">
            <HardHat className="text-hazard" size={26} />
          </div>
          <div className="leading-tight">
            <div className="flex items-center gap-2">
              <span className="text-white font-black tracking-[0.2em] text-sm">SITE-RISK</span>
              <span className="text-[9px] text-slate-500 readout border border-steel px-1 py-0.5">v2.0 · M2</span>
            </div>
            <div className="text-[9px] text-slate-500 readout tracking-[0.3em]">OPERATIONS CONTROL UNIT</div>
          </div>
        </div>

        {/* Center readouts */}
        <div className="hidden md:flex flex-1 items-center gap-6 px-6 readout text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 tracking-widest">SITE</span>
            <span className="text-slate-200 font-semibold">RV-TOWER-A1</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="led led-on" style={{ background: level.color, color: level.color }} />
            <span className="text-slate-500 tracking-widest">RISK</span>
            <span style={{ color: level.color }} className="font-bold">{level.label}</span>
            <span className="text-slate-400">{risk?.overall_score?.toFixed(1)}</span>
          </div>
          <div className="flex items-center gap-2">
            <Gauge className="text-slate-500" size={13} />
            <span className="text-slate-500 tracking-widest">MODE</span>
            <span className="text-info">DEMO / SIM</span>
          </div>
        </div>

        {/* Clock */}
        <div className="flex items-center gap-4 px-5 border-l border-steel">
          <div className="text-right readout">
            <div className="text-lg text-slate-100 font-semibold leading-none tabular-nums">{clock}</div>
            <div className="text-[9px] text-slate-500 tracking-widest">UTC · MONITOR</div>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-ok led led-on blink"></div>
        </div>
      </header>

      {/* ── hazard stripe divider ── */}
      <div className="hazard-bar h-1.5 w-full opacity-80"></div>

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left nav rail ── */}
        <aside className="w-64 shrink-0 border-r border-steel bg-[#0d1117] flex flex-col">
          <div className="p-3 border-b border-steel">
            <div className="bracket-label flex items-center justify-between">
              <span>Module Index</span><Crosshair className="text-info" size={12} />
            </div>
          </div>

          <nav className="flex-1 p-2 space-y-1">
            {NAV.map(({ to, label, icon: Icon, code }) => {
              const active = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
              return (
                <NavLink key={to} to={to} end={to === '/'}
                  className={({ isActive }) =>
                    `group relative flex items-center gap-2.5 px-3 py-2.5 readout text-[11px] tracking-wider border-l-2 transition-colors ${
                      isActive
                        ? 'border-hazard text-white bg-[#1b2431]'
                        : 'border-steel-2 text-slate-400 hover:text-white hover:bg-[#1b2431]'
                    }`
                  }>
                  <span className="text-slate-500 group-hover:text-slate-500 text-[10px]">{code}</span>
                  <Icon className={active ? 'text-hazard' : 'text-slate-500'} size={15} />
                  <span>{label}</span>
                </NavLink>
              )
            })}
          </nav>

          <div className="p-3 border-t border-steel">
            <div className="bracket-label mb-2">Telemetry Link</div>
            <div className="flex items-center gap-2 text-[11px] readout text-slate-400">
              <span className="led led-on bg-ok" /> Live conduit:
              <span className="text-ok">ACTIVE</span>
            </div>
            <div className="mt-1 text-[10px] text-slate-500 readout">ONE INPUT VIDEO · SHARED ANALYSIS PIPELINE</div>
          </div>
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 overflow-y-auto blueprint-bg">
          <Outlet />
        </main>
      </div>

      {/* ── bottom status bar ── */}
      <footer className="h-7 border-t border-steel bg-[#0e1218] flex items-center px-4 readout text-[10px] text-slate-500 gap-6">
        <span className="text-ok">● SYS ONLINE</span>
        <span className="text-slate-500">|</span>
        <span>MILESTONE 2 · SITE RISK + SAFETY AGENTS</span>
        <span className="text-slate-500">|</span>
        <span>PPE ENGINE: READY</span>
        <span className="ml-auto text-slate-500">ACRIP-00 / RT 23:59:59</span>
      </footer>
    </div>
  )
}
