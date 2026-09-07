import { useState, useEffect, useRef } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import {
  Camera, Upload, Loader2, Scan, CloudCog, ListTree, FileJson, ChevronDown,
  Package, Users, Truck, Play, RefreshCw,
} from 'lucide-react'
import { StatChip, Section } from '../components/progressive'

const PIPELINE = ['VIDEO INPUT', 'FRAME SAMPLE', 'YOLO + PPE', 'AGENTS', 'ANALYSIS RECORD']

export default function Video() {
  const siteId = useSite()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [sources, setSources] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const [selectedPath, setSelectedPath] = useState('')
  const fileRef = useRef(null)

  const loadSources = async () => {
    try {
      const res = await api.listVideoSources(siteId)
      setSources(res.data)
      if (res.data.default?.path && !selectedPath) setSelectedPath(res.data.default.path)
    } catch { /* backend may be offline */ }
  }
  useEffect(() => { loadSources() }, [siteId])

  const onFileChange = (e) => {
    const f = e.target.files?.[0]
    setError(null)
    if (!f) return
    setFile(f); setPreview(URL.createObjectURL(f)); setResult(null); setSelectedPath('')
  }

  const runAnalyze = async (opts = {}) => {
    setProcessing(true); setError(null); setResult(null)
    try {
      const res = await api.analyzeVideo(siteId, opts)
      setResult(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Analysis failed. Check the backend is on port 8001 and a video source exists.')
    } finally { setProcessing(false) }
  }

  const analyzeDefault = () => runAnalyze({ videoPath: selectedPath })
  const analyzeUpload = () => { if (file) runAnalyze({ file }) }

  const video = result?.video || {}
  const frameEvidence = result?.frame_evidence || []

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center gap-2">
        <Camera className="text-info" size={18} />
        <div>
          <h1 className="text-white font-black tracking-[0.15em] text-lg">COMPUTER VISION / DATASET BAY</h1>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">SINGLE INPUT VIDEO · REAL YOLO + PPE DETECTION</div>
        </div>
      </div>

      {/* pipeline strip */}
      <div className="hazard-bar h-1.5 w-56 opacity-70"></div>
      <div className="tech-panel p-3 flex flex-wrap items-center gap-2 readout text-[10px] text-slate-400">
        {PIPELINE.map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            <span className="bg-[#0a0e13] border border-steel px-2 py-1">{s}</span>
            {i < PIPELINE.length - 1 && <span className="text-hazard">›</span>}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        {/* Input hopper */}
        <div className="lg:col-span-2 tech-panel p-4 space-y-3">
          <div className="bracket-label flex items-center gap-1.5"><CloudCog size={12} /> INPUT HOPPER</div>

          {sources?.default && (
            <div className="bg-[#0a0e13] border border-steel p-3">
              <div className="readout text-[10px] text-slate-500 tracking-widest mb-1.5">PRIMARY INPUT VIDEO</div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Play className="text-ok shrink-0" size={14} />
                  <span className="readout text-[11px] text-slate-200 truncate">{sources.default.name}</span>
                </div>
                <span className="readout text-[9px] text-slate-500 shrink-0">{Math.round((sources.default.size_mb || 0) * 10) / 10} MB</span>
              </div>
              <button onClick={analyzeDefault} disabled={processing}
                className="mt-3 w-full flex items-center justify-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider py-2 transition">
                {processing ? <><Loader2 className="animate-spin" size={13} /> ANALYZING VIDEO...</> : <><Scan size={14} /> ANALYZE PRIMARY VIDEO</>}
              </button>
            </div>
          )}

          <div className="border-t border-steel pt-3">
            <label className="flex flex-col items-center justify-center border-2 border-dashed border-steel bg-[#0a0e13] p-6 cursor-pointer hover:border-hazard transition group">
              <Upload className="text-slate-500 group-hover:text-hazard mb-2" size={26} />
              <span className="text-sm text-slate-300">Select construction-site video</span>
              <span className="readout text-[10px] text-slate-500 mt-1">MP4 / MOV / MKV — workers, equipment, PPE</span>
              <input ref={fileRef} type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" onChange={onFileChange} className="hidden" />
            </label>

            {preview && (
              <div className="mt-3">
                <video src={preview} controls className="rounded-[4px] max-h-56 w-full bg-black border border-steel" />
                <button onClick={analyzeUpload} disabled={processing}
                  className="mt-3 w-full flex items-center justify-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider py-2 transition">
                  {processing ? <><Loader2 className="animate-spin" size={13} /> ANALYZING...</> : <><Scan size={14} /> ANALYZE UPLOADED VIDEO</>}
                </button>
              </div>
            )}
          </div>

          {error && <div className="readout text-[11px] text-signal bg-signal/10 border border-signal/40 p-2">⚠ {error}</div>}
        </div>

        {/* Results bay */}
        <div className="lg:col-span-3 tech-panel p-4">
          <div className="bracket-label mb-3 flex items-center justify-between">
            <span>ANALYSIS OUTPUT</span>
            {result && <span className="readout text-[9px] text-slate-500 tracking-widest">{result.video?.filename?.toUpperCase()} · {result.analysis_id?.slice(0, 8)}</span>}
          </div>

          {!preview && !result && (
            <div className="text-center py-16">
              <Camera className="mx-auto mb-3 text-slate-500" size={40} />
              <p className="text-sm text-slate-500">One construction-site video is the single source of truth.</p>
              <p className="readout text-[10px] text-slate-500 mt-1">RUN THE PIPELINE TO PRODUCE FRAME EVIDENCE + AGENT ANALYSIS</p>
            </div>
          )}

          {processing && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-400">
              <Loader2 className="animate-spin text-info" size={28} />
              <span className="readout text-[12px] tracking-widest">SAMPLING FRAMES › YOLO › PPE › AGENTS...</span>
            </div>
          )}

          {!processing && result && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatChip icon={Users} label="Workers" value={result.worker_count ?? 0} accent="#4aa8ff" />
                <StatChip icon={Truck} label="Vehicles" value={result.vehicle_count ?? 0} accent="#f5a623" />
                <StatChip icon={Package} label="Objects" value={result.detected_objects?.length ?? 0} accent="#36d17e" sub="best frame" />
                <StatChip icon={Camera} label="Frames" value={video.frames_analyzed ?? 0} accent="#b794ff" sub={`${video.frame_interval}f step`} />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatChip icon={Camera} label="Lighting" value={video.lighting_condition || '—'} accent="#4aa8ff" sub="from frames" />
                <StatChip icon={Users} label="PPE Compliance" value={`${result.ppe?.compliance ?? 0}%`} accent="#f5a623" />
                <StatChip icon={Package} label="Violations" value={result.ppe?.total_violations ?? 0} accent="#ff5a3c" />
                <StatChip icon={Truck} label="Equipment" value={result.equipment?.length ?? 0} accent="#36d17e" />
              </div>

              {result.evidence_note && (
                <div className="readout text-[10px] text-slate-400 border-l-2 border-steel-2 bg-[#0a0e13] p-2">
                  <span className="text-slate-500 tracking-widest">EVIDENCE NOTE: </span>{result.evidence_note}
                </div>
              )}

              {/* Tabs for heavy data */}
              <div className="grid grid-cols-3 gap-2">
                {[
                  { key: 'frames', label: 'Frame Samples', icon: Scan },
                  { key: 'equipment', label: 'Equipment', icon: Truck },
                  { key: 'raw', label: 'Raw JSON', icon: FileJson },
                ].map(({ key, label, icon: Icon }) => (
                  <button key={key} onClick={() => setDetail(detail === key ? null : key)}
                    className={`flex items-center justify-center gap-2 readout text-[10px] font-bold tracking-wider px-2 py-2 transition border ${
                      detail === key
                        ? 'bg-hazard text-black border-hazard'
                        : 'bg-panel-3 border border-steel-2 text-slate-200 hover:bg-steel hover:text-white'
                    }`}>
                    <Icon size={12} /> {label.toUpperCase()}
                  </button>
                ))}
              </div>

              {detail === 'frames' && (
                <Section title="FRAME SAMPLE EVIDENCE" badge={`${frameEvidence.length} SAMPLES`} onClose={() => setDetail(null)}>
                  <div className="max-h-[360px] overflow-y-auto space-y-1">
                    {frameEvidence.length === 0 && <div className="readout text-[11px] text-slate-500">NO FRAME EVIDENCE</div>}
                    {frameEvidence.map((f, i) => (
                      <div key={i} className="border-b border-steel/40 py-1.5 readout text-[11px]">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-400">FRAME t+{f.timestamp}s · <span className="text-info">{f.worker_count} WRK</span> · <span className="text-hazard">{f.vehicle_count} VEH</span></span>
                          <span className="text-slate-500">{f.violations} PPE</span>
                        </div>
                        {f.detections?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {f.detections.map((d, j) => (
                              <span key={j} className="readout text-[9px] px-1.5 py-0.5 border tracking-wider"
                                style={{ color: d.class_id === 0 ? '#4aa8ff' : '#f5a623', borderColor: d.class_id === 0 ? '#4aa8ff' : '#f5a623' }}>
                                {d.label}·{Math.round((d.confidence || 0) * 100)}%
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {detail === 'equipment' && (
                <Section title="EQUIPMENT (VIDEO-DERIVED)" badge={`${result.equipment?.length ?? 0} ASSETS`} onClose={() => setDetail(null)}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[360px] overflow-y-auto">
                    {(result.equipment || []).map((eq, i) => (
                      <div key={eq.id || i} className="flex items-center justify-between bg-[#0a0e13] border border-steel px-3 py-2">
                        <div className="readout">
                          <div className="text-[12px] text-slate-200 font-semibold">{eq.name}</div>
                          <div className="text-[9px] text-slate-500 tracking-wider uppercase">{eq.activity}</div>
                        </div>
                        <span className="readout text-[9px] px-1.5 py-0.5 font-semibold" style={{ color: '#36d17e', border: '1px solid #36d17e' }}>
                          {eq.status?.toUpperCase()}
                        </span>
                      </div>
                    ))}
                    {!result.equipment?.length && <div className="readout text-[11px] text-slate-500 col-span-2">NO EQUIPMENT DETECTED IN VIDEO</div>}
                  </div>
                </Section>
              )}

              {detail === 'raw' && (
                <Section title="RAW ANALYSIS OUTPUT" onClose={() => setDetail(null)}>
                  <button onClick={() => setShowRaw(!showRaw)}
                    className="flex items-center gap-1.5 readout text-[10px] text-slate-500 hover:text-white mb-2">
                    <RefreshCw size={12} /> {showRaw ? 'HIDE ' : 'VIEW '}FULL RESPONSE <ChevronDown size={12} className={showRaw ? 'rotate-180' : ''} />
                  </button>
                  {showRaw && (
                    <pre className="text-[10px] text-slate-400 bg-[#080b0f] border border-steel p-3 overflow-auto max-h-72">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  )}
                </Section>
              )}

              <div className="readout text-[10px] text-ok">ANALYSIS {result.analysis_id?.slice(0, 13)}… → SHARED BY RISK · SAFETY · MONITORING</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}