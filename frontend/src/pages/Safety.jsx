import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import {
  HardHat, ShieldAlert, AlertTriangle, Users, Activity, ImageIcon,
  ChevronDown, X, Eye, RefreshCw, FileJson,
} from 'lucide-react'

const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const LEVEL_BG = {
  LOW: 'rgba(54,209,126,0.12)', MEDIUM: 'rgba(245,166,35,0.12)',
  HIGH: 'rgba(255,122,60,0.14)', CRITICAL: 'rgba(255,90,60,0.16)',
}

function SafetyDial({ score, level }) {
  const color = LEVEL_HEX[level] || '#36d17e'
  const R = 52, C = 2 * Math.PI * R
  const filled = (score / 100) * C
  return (
    <div className="relative w-40 h-40 mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={R} fill="none" stroke="#1c2530" strokeWidth="8" />
        <circle cx="60" cy="60" r={R} fill="none" stroke={color} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={`${filled} ${C}`} style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="readout text-4xl font-black text-white tabular-nums">{score.toFixed(0)}</div>
        <div className="readout text-xs font-bold tracking-[0.2em] mt-0.5" style={{ color }}>{level}</div>
        <div className="text-[9px] text-slate-500 readout tracking-widest mt-0.5">SAFETY LEVEL</div>
      </div>
    </div>
  )
}

function StatChip({ icon: Icon, label, value, accent, sub }) {
  return (
    <div className="tech-panel p-4 flex items-center gap-3">
      <div className="w-9 h-9 shrink-0 rounded-[4px] border border-steel bg-panel-3 flex items-center justify-center"
        style={{ color: accent }}>
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <div className="readout text-2xl font-black text-white tabular-nums leading-none">{value}</div>
        <div className="readout text-[9px] text-slate-500 tracking-widest mt-1 uppercase truncate">{label}</div>
        {sub && <div className="readout text-[9px] text-slate-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

/* Bounding-box overlay drawn over the analyzed image, scaled to display size. */
function DetectionOverlay({ src, detections, imgW, imgH, mode }) {
  const ref = useRef(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv || !src) return
    const ctx = cv.getContext('2d')
    const img = new Image()
    img.onload = () => {
      cv.width = img.width
      cv.height = img.height
      ctx.clearRect(0, 0, cv.width, cv.height)
      ctx.drawImage(img, 0, 0)
      const sx = img.width / (imgW || 1)
      const sy = img.height / (imgH || 1)
      ;(detections || []).forEach((d) => {
        const [x1, y1, x2, y2] = d.bbox || []
        if (x1 == null) return
        const color = (d.class_name && String(d.class_name).includes('no_')) || (d.label && d.label.startsWith('no_'))
          ? '#ff5a3c' : '#4aa8ff'
        ctx.strokeStyle = color
        ctx.lineWidth = Math.max(2, img.width / 500)
        ctx.strokeRect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy)
        const label = (d.class_name || d.label || '') + (d.confidence ? ` ${(d.confidence * 100).toFixed(0)}%` : '')
        ctx.font = `${Math.max(11, img.width / 70)}px ui-monospace`
        ctx.fillStyle = color
        ctx.fillRect(x1 * sx, y1 * sy - 18, ctx.measureText(label).width + 8, 18)
        ctx.fillStyle = '#0b0f14'
        ctx.fillText(label, x1 * sx + 4, y1 * sy - 4)
      })
    }
    img.src = src
  }, [src, detections, imgW, imgH, mode])
  return (
    <div className="relative w-full border border-steel bg-black" style={{ maxHeight: 560, overflow: 'hidden' }}>
      <canvas ref={ref} className="w-full h-auto" />
    </div>
  )
}

export default function Safety() {
  const siteId = useSite()
  const [data, setData] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState(null) // 'workers' | 'violations' | 'alerts' | 'zones'

  // Image analysis state
  const [img, setImg] = useState(null)         // { src, width, height }
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [analysisError, setAnalysisError] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const fileRef = useRef(null)

  const load = async () => {
    try {
      const res = await api.getSafetyDashboard(siteId)
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message || 'Failed to load safety dashboard')
    }
  }
  useEffect(() => { load() }, [siteId])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.getSafetyAnalysis(siteId); await load() } finally { setRunning(false) }
  }

  const selectImage = (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file) return
    const src = URL.createObjectURL(file)
    const tmp = new Image()
    tmp.onload = () => { setImg({ src, width: tmp.width, height: tmp.height, file }); setAnalysis(null); setAnalysisError(null); setShowRaw(false) }
    tmp.src = src
  }

  const analyzeImage = async () => {
    if (!img) return
    setAnalyzing(true)
    try {
      const res = await api.processImage(siteId, img.file)
      setAnalysis(res.data)
      setAnalysisError(res.data?.ppe_error || null)
    } catch (err) {
      setAnalysisError(err?.message || 'Image analysis failed')
      setAnalysis(null)
    } finally { setAnalyzing(false) }
  }

  if (error && !data) {
    return (
      <div className="p-6">
        <div className="tech-panel p-5 border-l-signal">
          <p className="readout text-signal font-bold">⚠ SYS OFFLINE — {error}</p>
          <p className="readout text-slate-400 text-xs mt-2">Run safety analysis to seed worker data.</p>
        </div>
      </div>
    )
  }

  const assess = data?.current_safety_assessment
  const level = assess?.overall_safety_level || 'LOW'
  const violations = data?.violations || []
  const alerts = (data?.alerts || []).filter((a) => a.severity === 'CRITICAL' || a.severity === 'HIGH')
  const highRiskZones = (data?.accident_zone_data || []).filter((z) => z.risk_level === 'HIGH' || z.risk_level === 'CRITICAL')

  const tabs = [
    { key: 'workers', label: 'Workers', icon: Users },
    { key: 'violations', label: 'PPE Violations', icon: ShieldAlert },
    { key: 'alerts', label: 'Alerts', icon: AlertTriangle },
    { key: 'zones', label: 'Accident Zones', icon: Activity },
  ]

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <HardHat className="text-hazard" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">SAFETY INTELLIGENCE</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">WORKER PROTECTION · PPE COMPLIANCE · IMAGE ANALYSIS · M2</div>
        </div>
        <button onClick={runAnalysis} disabled={running}
          className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
          <RefreshCw size={13} className={running ? 'animate-spin' : ''} /> {running ? 'ANALYZING...' : 'REFRESH SITE SAFETY'}
        </button>
      </div>
      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      {/* ── Primary overview: score + key metrics ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
        <div className="lg:col-span-1 tech-panel p-4 flex flex-col items-center justify-center">
          <div className="bracket-label self-start mb-2 flex items-center gap-1.5"><ShieldAlert size={12} /> OVERALL SAFETY</div>
          <SafetyDial score={assess?.overall_safety_score || 0} level={level} />
          <p className="readout text-[10px] text-slate-500 mt-3 text-center leading-relaxed">{assess?.summary}</p>
        </div>

        <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatChip icon={AlertTriangle} label="Critical Alerts" value={data?.critical_alerts ?? 0}
            accent="#ff5a3c" sub={`${alerts.length} HIGH+`} />
          <StatChip icon={ShieldAlert} label="Active Violations" value={data?.open_violations ?? 0}
            accent="#f5a623" />
          <StatChip icon={Users} label="Workers Monitored" value={data?.total_workers ?? 0}
            accent="#4aa8ff" sub={`${data?.compliant_workers ?? 0} compliant`} />
          <StatChip icon={Activity} label="High-Risk Zones" value={highRiskZones.length}
            accent="#ff7a3c" />
        </div>
      </div>

      {/* ── Secondary: compliance rate bar ── */}
      <div className="tech-panel p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="bracket-label">PPE COMPLIANCE RATE</span>
          <span className="readout text-xl font-bold text-white tabular-nums">{Math.round((assess?.ppe_compliance_rate ?? 1) * 100)}%</span>
        </div>
        <div className="h-1.5 bg-[#0a0e13] border border-steel rounded-full overflow-hidden">
          <div className="h-full" style={{ width: `${Math.round((assess?.ppe_compliance_rate ?? 1) * 100)}%`, background: '#36d17e', boxShadow: '0 0 8px #36d17e' }} />
        </div>
      </div>

      {/* ── Action bar ── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <button onClick={() => fileRef.current?.click()}
          className="flex items-center justify-center gap-2 bg-info hover:bg-[#3a8ee6] text-black readout text-[11px] font-bold tracking-wider px-3 py-3 transition">
          <ImageIcon size={15} /> ANALYZE IMAGE
        </button>
        {tabs.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(tab === key ? null : key)}
            className={`flex items-center justify-center gap-2 readout text-[11px] font-bold tracking-wider px-3 py-3 transition border ${
              tab === key
                ? 'bg-hazard text-black border-hazard'
                : 'bg-panel border-steel text-slate-300 hover:bg-panel-3 hover:text-white'
            }`}>
            <Icon size={13} /> {label.toUpperCase()}
          </button>
        ))}
      </div>
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={selectImage} />

      {/* ── Image analysis panel ── */}
      {(analysis || analysisError || img) && (
        <div className="tech-panel p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="bracket-label flex items-center gap-1.5"><ImageIcon size={12} /> IMAGE ANALYSIS <span className="text-slate-600">· REAL YOLO INFERENCE</span></span>
            <button onClick={() => { setImg(null); setAnalysis(null); setAnalysisError(null); setShowRaw(false) }}
              className="readout text-[10px] text-slate-500 hover:text-white flex items-center gap-1"><X size={11} /> CLEAR</button>
          </div>

          {!analysis && !analysisError && (
            <div className="flex flex-col items-center gap-3 py-6">
              <p className="readout text-xs text-slate-400">Image selected — ready to analyze ({img?.width}×{img?.height})</p>
              <button onClick={analyzeImage} disabled={analyzing}
                className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider px-4 py-2 transition">
                {analyzing ? <><RefreshCw size={13} className="animate-spin" /> PROCESSING...</> : <><Eye size={13} /> ANALYZE IMAGE</>}
              </button>
            </div>
          )}

          {analyzing && (
            <div className="flex items-center gap-2 text-slate-400 readout text-xs py-6">
              <RefreshCw size={14} className="animate-spin text-info" /> Running real YOLO inference on uploaded image…
            </div>
          )}

          {analysisError && !analysis && (
            <div className="border-l-2 border-signal bg-signal/10 p-3 mb-3">
              <p className="readout text-[12px] text-signal font-bold">PPE MODEL UNAVAILABLE</p>
              <p className="readout text-[11px] text-slate-300 mt-1">{analysisError}</p>
            </div>
          )}

          {analysis && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <DetectionOverlay
                  src={img?.src}
                  detections={analysis.ppe_compliance?.detections || analysis.detections || []}
                  imgW={analysis.ppe_compliance?.image_width || analysis.image_width}
                  imgH={analysis.ppe_compliance?.image_height || analysis.image_height}
                />
                <div className="mt-2 text-[10px] text-slate-500 readout">
                  {analysis.worker_count} COCO person(s) · {analysis.vehicle_count} vehicle(s) · {analysis.detections?.length} base detections
                </div>
              </div>

              <div className="space-y-3">
                {analysis.ppe_compliance?.available === false ? (
                  <div className="border-l-2 border-signal bg-signal/10 p-3">
                    <p className="readout text-[12px] text-signal font-bold">PPE MODEL UNAVAILABLE</p>
                    <p className="readout text-[11px] text-slate-300 mt-1">{analysis.ppe_compliance?.error}</p>
                    <p className="readout text-[10px] text-slate-500 mt-1">Base object detection above is real; PPE compliance was not fabricated.</p>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="bracket-label">PPE / SAFETY RESULT</span>
                      <span className="readout text-[10px] text-slate-500 flex items-center gap-2">
                        MODEL: {analysis.ppe_compliance?.model_used?.toUpperCase()}
                        <span className="led led-on bg-ok" />
                      </span>
                    </div>
                    <div className="flex items-center justify-between bg-[#0a0e13] border border-steel px-3 py-2">
                      <span className="readout text-[11px] text-slate-400">Safety Level</span>
                      <span className="readout text-lg font-black" style={{ color: LEVEL_HEX[analysis.ppe_compliance?.overall_safety_level] }}>
                        {analysis.ppe_compliance?.overall_safety_level} · {analysis.ppe_compliance?.overall_safety_score?.toFixed(0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between bg-[#0a0e13] border border-steel px-3 py-2">
                      <span className="readout text-[11px] text-slate-400">Workers / Compliance</span>
                      <span className="readout text-[12px] text-white">
                        {analysis.ppe_compliance?.workers?.length} · {Math.round((analysis.ppe_compliance?.compliance_rate ?? 1) * 100)}%
                        <span className="text-ok"> ✓{analysis.ppe_compliance?.compliant_count}</span>
                        <span className="text-signal"> ✗{analysis.ppe_compliance?.non_compliant_count}</span>
                      </span>
                    </div>

                    {/* Detected classes */}
                    <div className="bg-[#0a0e13] border border-steel p-3">
                      <div className="bracket-label mb-2">DETECTED CLASSES</div>
                      <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                        {(analysis.ppe_compliance?.detections || []).map((d, i) => {
                          const isMiss = String(d.class_name).includes('no_')
                          return (
                            <span key={i} className="readout text-[9px] px-1.5 py-0.5 border tracking-wider"
                              style={isMiss
                                ? { color: '#ff5a3c', borderColor: '#ff5a3c' }
                                : { color: '#4aa8ff', borderColor: '#4aa8ff' }}>
                              {d.class_name}·{Math.round(d.confidence * 100)}%
                            </span>
                          )
                        })}
                      </div>
                    </div>

                    {/* Compliance details */}
                    <div className="bg-[#0a0e13] border border-steel p-3 max-h-40 overflow-y-auto">
                      <div className="bracket-label mb-2">WORKER PPE STATUS</div>
                      {(analysis.ppe_compliance?.workers || []).map((w) => (
                        <div key={w.worker_id} className="flex items-center justify-between py-1 border-b border-steel/40 last:border-0">
                          <span className="readout text-[10px] text-slate-300">{w.worker_id} · {w.worker_role}</span>
                          <span className="readout text-[10px]" style={{ color: w.ppe_status === 'compliant' ? '#36d17e' : '#ff7a3c' }}>
                            {w.ppe_status === 'compliant' ? 'COMPLIANT' : `MISSING: ${(w.missing_ppe || []).join(' ').replace(/_/g, ' ').toUpperCase() || 'PPE'}`}
                          </span>
                        </div>
                      ))}
                      {(analysis.ppe_compliance?.workers || []).length === 0 && (
                        <span className="readout text-[10px] text-slate-500">No persons detected in this image.</span>
                      )}
                    </div>

                    {/* Recommendations */}
                    {(analysis.ppe_compliance?.recommendations || []).length > 0 && (
                      <div className="bg-[#0a0e13] border border-steel p-3">
                        <div className="bracket-label mb-2">RECOMMENDATIONS</div>
                        <ul className="space-y-1 max-h-28 overflow-y-auto">
                          {analysis.ppe_compliance.recommendations.map((r, i) => (
                            <li key={i} className="readout text-[10px] text-slate-300 flex gap-1.5">
                              <span className="text-hazard">▸</span>{r.title}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}

                {/* Raw response accordion */}
                <button onClick={() => setShowRaw(!showRaw)}
                  className="flex items-center gap-1.5 readout text-[10px] text-slate-500 hover:text-white">
                  <FileJson size={12} /> {showRaw ? 'HIDE ' : 'VIEW '}RAW RESPONSE <ChevronDown size={12} className={showRaw ? 'rotate-180' : ''} />
                </button>
                {showRaw && (
                  <pre className="text-[10px] text-slate-400 bg-[#080b0f] border border-steel p-3 overflow-auto max-h-72">
                    {JSON.stringify(analysis, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Detail tabs (progressive disclosure) ── */}
      {tab === 'workers' && (
        <Section title="WORKER PPE REGISTER" onClose={() => setTab(null)}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {(data?.workers || []).map((w) => (
              <div key={w.id} className="flex items-center justify-between bg-[#0a0e13] border border-steel px-3 py-2">
                <div className="min-w-0">
                  <div className="readout text-[12px] text-slate-200 font-semibold truncate">{w.name}</div>
                  <div className="text-[9px] text-slate-500 tracking-wider uppercase">{w.role}{w.missing_ppe?.length ? ` · ${w.missing_ppe.join(', ').replace(/_/g, ' ')}` : ''}</div>
                </div>
                <span className="readout text-[9px] px-1.5 py-0.5 font-semibold shrink-0"
                  style={w.ppe_status === 'compliant'
                    ? { color: '#36d17e', border: '1px solid #36d17e' }
                    : { color: '#ff5a3c', border: '1px solid #ff5a3c' }}>
                  {w.ppe_status === 'compliant' ? 'COMPLIANT' : 'VIOLATION'}
                </span>
              </div>
            ))}
            {(data?.workers || []).length === 0 && <div className="readout text-[11px] text-slate-500 col-span-2">NO WORKER DATA — RUN SITE SAFETY ANALYSIS</div>}
          </div>
        </Section>
      )}

      {tab === 'violations' && (
        <Section title="SAFETY VIOLATION REGISTER" onClose={() => setTab(null)}>
          <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
            {violations.map((v) => {
              const c = LEVEL_HEX[v.severity] || '#36d17e'
              return (
                <div key={v.id} className="flex items-start justify-between gap-2 bg-[#0a0e13] border border-steel p-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="readout text-[9px] font-bold px-1 py-0.5 mt-0.5" style={{ color: c, border: `1px solid ${c}`, background: LEVEL_BG[v.severity] || 'transparent' }}>{v.severity}</span>
                    <div className="min-w-0">
                      <div className="readout text-[11px] text-slate-200">{v.description}</div>
                      <div className="readout text-[9px] text-slate-500 mt-0.5">{v.violation_type.replace(/_/g, ' ')} · {v.source} · {formatTime(v.timestamp)}</div>
                    </div>
                  </div>
                  <span className="readout text-[9px] text-slate-400 shrink-0" style={{ color: v.status === 'open' ? '#f5a623' : '#36d17e' }}>{v.status.toUpperCase()}</span>
                </div>
              )
            })}
            {violations.length === 0 && <div className="readout text-[11px] text-slate-500">NO VIOLATIONS</div>}
          </div>
        </Section>
      )}

      {tab === 'alerts' && (
        <Section title="SAFETY ALERT FEED" onClose={() => setTab(null)}>
          <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
            {(data?.alerts || []).map((a) => {
              const c = LEVEL_HEX[a.severity] || '#36d17e'
              return (
                <div key={a.id} className="border-l-2 pl-2 py-1.5 mb-1.5 bg-[#0a0e13] border-b border-steel/30">
                  <div className="flex items-center justify-between">
                    <span className="readout text-[9px] font-bold tracking-widest" style={{ color: c }}>{a.alert_type.replace(/_/g, ' ').toUpperCase()}</span>
                    <span className="readout text-[9px] text-slate-500">{formatTime(a.timestamp)}</span>
                  </div>
                  <p className="readout text-[10px] text-slate-300 mt-1 leading-relaxed">{a.message}</p>
                </div>
              )
            })}
            {(data?.alerts || []).length === 0 && <div className="readout text-[11px] text-slate-500">NO ACTIVE ALERTS</div>}
          </div>
        </Section>
      )}

      {tab === 'zones' && (
        <Section title="ACCIDENT-PRONE ZONES" onClose={() => setTab(null)}>
          <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
            {(data?.accident_zone_data || []).map((z) => {
              const c = LEVEL_HEX[z.risk_level] || '#36d17e'
              return (
                <div key={z.zone_id} className="flex items-center justify-between bg-[#0a0e13] border border-steel p-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="led led-on" style={{ background: c, color: c }} />
                    <span className="readout text-[12px] text-slate-300 truncate">{z.zone_name}</span>
                  </div>
                  <span className="readout text-[10px] font-bold" style={{ color: c }}>{z.risk_level} · {z.current_risk_score?.toFixed(0)}</span>
                </div>
              )
            })}
            {(data?.accident_zone_data || []).length === 0 && <div className="readout text-[11px] text-slate-500">NO ZONE DATA</div>}
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, onClose, children }) {
  return (
    <div className="tech-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="bracket-label">{title}</span>
        <button onClick={onClose} className="readout text-[10px] text-slate-500 hover:text-white flex items-center gap-1"><X size={11} /> CLOSE</button>
      </div>
      {children}
    </div>
  )
}
