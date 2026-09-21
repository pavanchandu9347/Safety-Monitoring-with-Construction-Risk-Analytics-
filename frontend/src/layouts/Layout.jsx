import { useState, useEffect, useRef, useCallback } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, ShieldAlert, Activity, Camera, Radio, HardHat,
  Crosshair, ShieldCheck, Bell, LogOut, BrainCircuit, FileText,
  CheckCheck, User as UserIcon
} from 'lucide-react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { useAuth } from '../contexts/AuthContext'

const RISK_LEVELS = {
  LOW: { label: 'LOW', color: '#36d17e' },
  MEDIUM: { label: 'MEDIUM', color: '#f5a623' },
  HIGH: { label: 'HIGH', color: '#ff7a3c' },
  CRITICAL: { label: 'CRITICAL', color: '#ff5a3c' },
}

const SEVERITY_COLORS = {
  LOW: '#36d17e',
  MEDIUM: '#f5a623',
  HIGH: '#ff7a3c',
  CRITICAL: '#ff5a3c',
}

const NAV = [
  { to: '/', label: 'OPS. DASHBOARD', icon: LayoutDashboard, code: '01' },
  { to: '/monitoring', label: 'SENSOR FEED', icon: Radio, code: '02' },
  { to: '/video', label: 'CV / DATASET', icon: Camera, code: '03' },
  { to: '/hazards', label: 'HAZARD LOG', icon: ShieldAlert, code: '04' },
  { to: '/analysis', label: 'RISK ANALYSIS', icon: Activity, code: '05' },
  { to: '/safety', label: 'SAFETY CTL', icon: HardHat, code: '06' },
  { to: '/compliance', label: 'COMPLIANCE', icon: ShieldCheck, code: '07' },
  { to: '/insurance', label: 'INSURANCE', icon: ShieldAlert, code: '08' },
  { to: '/intelligence', label: 'INTELLIGENCE', icon: BrainCircuit, code: '09' },
  { to: '/reports', label: 'REPORTS', icon: FileText, code: '10' },
]

function sourcePath(type) {
  if (type === 'risk_alert') return '/analysis'
  if (type === 'safety_alert' || type === 'ppe_alert') return '/safety'
  if (type === 'incident') return '/insurance'
  return '/analysis'
}

function timeAgo(iso) {
  if (!iso) return ''
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export default function Layout() {
  const siteId = useSite()
  const { manager, logout } = useAuth()
  const navigate = useNavigate()
  const [risk, setRisk] = useState(null)
  const location = useLocation()

  // Notification bell state
  const [bellOpen, setBellOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unread, setUnread] = useState(0)
  const [bellLoading, setBellLoading] = useState(false)
  const bellRef = useRef(null)

  const refreshUnread = useCallback(() => {
    api.getUnreadCount().then((r) => setUnread(r.data.count)).catch(() => {})
  }, [])

  const loadNotifications = useCallback(async () => {
    setBellLoading(true)
    try {
      const res = await api.getNotifications({ limit: 30 })
      setNotifications(res.data || [])
    } catch {
      /* ignore */
    } finally {
      setBellLoading(false)
    }
  }, [])

  useEffect(() => {
    api.getCurrentRisk(siteId).then((r) => setRisk(r.data)).catch(() => {})
  }, [siteId])

  useEffect(() => {
    refreshUnread()
    const id = setInterval(refreshUnread, 20000)
    return () => clearInterval(id)
  }, [refreshUnread])

  // Close the bell dropdown when clicking elsewhere.
  useEffect(() => {
    const onDoc = (e) => {
      if (bellRef.current && !bellRef.current.contains(e.target)) setBellOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const toggleBell = async () => {
    const next = !bellOpen
    setBellOpen(next)
    if (next) {
      loadNotifications()
    }
  }

  const openNotification = async (n) => {
    if (n.status === 'unread') {
      try {
        await api.markNotificationRead(n.id)
        setUnread((u) => Math.max(0, u - 1))
        setNotifications((list) => list.map((x) => (x.id === n.id ? { ...x, status: 'read' } : x)))
      } catch {
        /* ignore */
      }
    }
    setBellOpen(false)
    navigate(sourcePath(n.type))
  }

  const markAllRead = async () => {
    try {
      await api.markAllNotificationsRead(siteId)
      setUnread(0)
      setNotifications((list) => list.map((x) => ({ ...x, status: 'read' })))
    } catch {
      /* ignore */
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

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
              <span className="text-white font-black tracking-[0.2em] text-sm">BUILDSURE</span>
              <span className="text-[9px] text-slate-500 readout border border-steel px-1 py-0.5">v4.0 · M4</span>
            </div>
            <div className="text-[9px] text-slate-500 readout tracking-[0.3em]">CONSTRUCTION RISK INTELLIGENCE</div>
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
        </div>

        <div className="flex items-center gap-1 pr-1">

          {/* ── Notification bell ── */}
          <div className="relative" ref={bellRef}>
            <button
              onClick={toggleBell}
              aria-label="Notifications"
              className="relative flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-white hover:bg-[#151a21] transition-colors"
            >
              <Bell size={18} />
              {unread > 0 && (
                <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 rounded-full bg-signal text-[9px] font-bold text-white flex items-center justify-center">
                  {unread > 99 ? '99+' : unread}
                </span>
              )}
            </button>

            {bellOpen && (
              <div className="absolute right-0 top-[46px] w-[380px] max-h-[540px] border border-steel bg-[#0d1117] shadow-2xl rounded-[6px] overflow-hidden z-50 flex flex-col">
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-steel bg-[#11161d]">
                  <span className="readout text-[10px] tracking-widest text-slate-400">
                    RISK ALERTS {unread > 0 ? `· ${unread} UNREAD` : ''}
                  </span>
                  <button
                    onClick={markAllRead}
                    disabled={unread === 0}
                    className="flex items-center gap-1 text-[10px] readout tracking-widest text-info hover:text-white disabled:opacity-40"
                  >
                    <CheckCheck size={12} /> MARK ALL READ
                  </button>
                </div>

                <div className="overflow-y-auto flex-1">
                  {bellLoading && notifications.length === 0 && (
                    <div className="p-6 text-center text-sm text-slate-500 readout">LOADING ALERTS…</div>
                  )}
                  {!bellLoading && notifications.length === 0 && (
                    <div className="p-6 text-center text-sm text-slate-500 readout">NO ALERTS</div>
                  )}
                  {notifications.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => openNotification(n)}
                      className="w-full text-left flex gap-3 px-4 py-3 border-b border-steel-2/40 hover:bg-[#151b23] transition-colors"
                    >
                      <span
                        className="mt-1.5 w-2 h-2 rounded-full shrink-0"
                        style={{ background: SEVERITY_COLORS[n.severity] || '#f5a623' }}
                      />
                      <span className="flex-1 min-w-0">
                        <span className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white truncate">{n.title}</span>
                          {n.status === 'unread' && (
                            <span className="shrink-0 text-[9px] readout tracking-widest text-signal border border-signal/50 px-1.5 py-px rounded">NEW</span>
                          )}
                        </span>
                        <span className="block text-xs text-slate-400 mt-0.5 line-clamp-2">{n.message}</span>
                        <span className="flex items-center gap-2 mt-1.5 readout text-[9px] tracking-widest text-slate-500">
                          <span style={{ color: SEVERITY_COLORS[n.severity] }}>{n.severity}</span>
                          {n.risk_score != null && <span>· SCORE {n.risk_score?.toFixed(0)}</span>}
                          {n.analysis_id && <span>· ANA {n.analysis_id.slice(0, 8)}</span>}
                          <span className="ml-auto">{timeAgo(n.created_at)}</span>
                        </span>
                        {!n.evidence_available && (
                          <span className="block mt-1 text-[10px] readout text-slate-600">EVIDENCE: UNAVAILABLE</span>
                        )}
                      </span>
                    </button>
                  ))}
                </div>

                <div className="px-4 py-2 border-t border-steel bg-[#11161d] readout text-[9px] tracking-widest text-slate-600">
                  ALERTS ARE DERIVED FROM REAL ANALYSIS EVIDENCE
                </div>
              </div>
            )}
          </div>

          {/* ── Manager profile / logout ── */}
          <div className="flex items-center gap-2 pl-3 pr-4 py-2 border-l border-steel">
            <div className="text-right leading-tight max-w-[170px]">
              <div className="text-xs font-semibold text-slate-100 truncate">{manager?.name || 'Manager'}</div>
              <div className="text-[9px] text-slate-500 readout tracking-wider truncate">{manager?.email}</div>
            </div>
            <div className="w-8 h-8 rounded-[4px] bg-[#151a21] border border-steel flex items-center justify-center">
              <UserIcon className="text-info" size={15} />
            </div>
            <button
              onClick={handleLogout}
              aria-label="Sign out"
              className="ml-1 p-1.5 text-slate-500 hover:text-signal hover:bg-[#151a21] rounded-[4px] transition-colors"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
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
        <span>MILESTONE 4 · REPORTING INTELLIGENCE + ENTERPRISE DEPLOYMENT</span>
        <span className="text-slate-500">|</span>
        <span>PPE ENGINE: READY</span>
        <span className="ml-auto text-slate-500">BUILDSURE-00 / RT 24:00:00</span>
      </footer>
    </div>
  )
}