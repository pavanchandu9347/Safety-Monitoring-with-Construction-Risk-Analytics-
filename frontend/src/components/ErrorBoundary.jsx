import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info)
  }

  render() {
    if (this.state.error) {
      const message = String(this.state.error && this.state.error.message ? this.state.error.message : this.state.error)
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#0b0f14] p-6">
          <div className="tech-panel max-w-xl w-full p-6 border-l-4 border-l-signal space-y-3">
            <div className="readout text-hazard font-black tracking-[0.2em]">RUNTIME ERROR — APP PAUSED SAFELY</div>
            <p className="readout text-[11px] text-slate-300">
              A component crashed while rendering. The app is paused instead of showing a blank screen.
              Reload to resume. If it persists, check the browser console for the full stack trace.
            </p>
            <pre className="readout text-[10px] text-signal bg-[#0a0e13] border border-steel p-3 overflow-x-auto whitespace-pre-wrap max-h-48">
              {message}
            </pre>
            <div className="flex gap-2">
              <button
                onClick={() => window.location.reload()}
                className="readout text-[11px] font-bold tracking-wider bg-hazard hover:bg-hazard-2 text-black px-4 py-2 transition"
              >
                RELOAD
              </button>
              <button
                onClick={() => {
                  const keys = ['buildsure_token', 'buildsure_manager']
                  keys.forEach((k) => localStorage.removeItem(k))
                  window.location.href = '/login'
                }}
                className="readout text-[11px] font-bold tracking-wider border border-steel text-slate-200 hover:bg-steel px-4 py-2 transition"
              >
                CLEAR SESSION & LOGIN
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}