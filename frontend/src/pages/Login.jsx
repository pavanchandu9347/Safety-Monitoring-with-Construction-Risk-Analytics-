import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { HardHat, Eye, EyeOff, Loader2, CircleAlert, KeyRound, Tag } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { manager, loading, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await login(email, password)
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) {
        setError('Invalid email or password. Contact your site administrator.')
      } else {
        setError(err?.response?.data?.detail || err.message || 'Unable to sign in. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0b0f14]">
        <Loader2 className="animate-spin text-hazard" size={28} />
      </div>
    )
  }

  if (manager) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen flex bg-[#0b0f14]">
      {/* ── Brand panel ── */}
      <div className="hidden lg:flex w-[46%] flex-col justify-between p-10 border-r border-steel bg-[#0e1218] relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-30" style={{
          backgroundImage: `linear-gradient(rgba(74,168,255,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(74,168,255,0.12) 1px, transparent 1px)`,
          backgroundSize: '28px 28px',
        }} />
        <div className="relative flex items-center gap-3">
          <div className="w-12 h-12 rounded-[4px] bg-[#151a21] border border-steel flex items-center justify-center shadow-inner">
            <HardHat className="text-hazard" size={28} />
          </div>
          <div className="leading-tight">
            <div className="text-white font-black tracking-[0.25em] text-lg">BUILDSURE</div>
            <div className="text-[10px] text-slate-500 readout tracking-[0.3em]">CONSTRUCTION RISK INTELLIGENCE PLATFORM</div>
          </div>
        </div>
        <div className="relative space-y-6">
          <h1 className="text-3xl font-black tracking-tight text-white leading-tight">
            Manager Authentication
            <br />
            <span className="text-hazard">Intelligent Risk Alerts</span>
          </h1>
          <ul className="space-y-3 text-sm text-slate-400">
            <li className="flex items-center gap-2"><span className="led led-on bg-ok" /> Per-site authorized access control</li>
            <li className="flex items-center gap-2"><span className="led led-on bg-ok" /> Evidence-based, real-time alerting</li>
            <li className="flex items-center gap-2"><span className="led led-on bg-ok" /> Every notification traced to real analysis data</li>
          </ul>
        </div>
        <div className="relative readout text-[10px] text-slate-600 tracking-widest">BUILDSURE · OPERATIONS CONTROL · M4</div>
      </div>

      {/* ── Form panel ── */}
      <div className="flex-1 flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5">
          <div className="mb-2">
            <div className="bracket-label mb-3">AUTHORIZED MANAGER SIGN-IN</div>
            <h2 className="text-xl font-bold text-white">Sign in to the control unit</h2>
            <p className="text-sm text-slate-500 mt-1">Enter your account credentials to continue.</p>
          </div>

          {error && (
            <div className="flex items-center gap-2 border border-signal/40 bg-signal/10 text-signal text-sm px-3 py-2.5 rounded-[4px]">
              <CircleAlert size={15} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-2">
            <label className="readout text-[10px] tracking-widest text-slate-500">EMAIL</label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="manager@buildsure.io"
                className="w-full bg-panel border border-steel rounded-[4px] pl-9 pr-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-hazard"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="readout text-[10px] tracking-widest text-slate-500">PASSWORD</label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
              <input
                type={show ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-panel border border-steel rounded-[4px] pl-9 pr-10 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-hazard"
              />
              <button
                type="button"
                onClick={() => setShow(!show)}
                aria-label={show ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {show ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 bg-hazard text-black font-bold tracking-widest text-sm py-3 rounded-[4px] hover:bg-hazard-2 disabled:opacity-60 disabled:cursor-not-allowed readout"
          >
            {submitting ? <Loader2 size={15} className="animate-spin" /> : <span>SIGN IN</span>}
          </button>

          <p className="text-[10px] readout text-slate-600 tracking-wider text-center">
            PROTECTED AREA · ALL SITE ACTIONS ARE AUDITED
          </p>
        </form>
      </div>
    </div>
  )
}