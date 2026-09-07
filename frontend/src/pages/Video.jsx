import { useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { Camera, Upload, Loader2, Scan, CloudCog, ListTree, FileJson, ChevronDown, Package, Users, Truck } from 'lucide-react'
import { StatChip, Section, ActionBar } from '../components/progressive'

function Spinner() { return <Loader2 className="animate-spin" size={15} /> }

export default function Video() {
  const siteId = useSite()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)
  const [showRaw, setShowRaw] = useState(false)

  const onFileChange = (e) => {
    const f = e.target.files?.[0]
    setError(null)
    if (!f) return
    setFile(f); setPreview(URL.createObjectURL(f)); setResult(null)
  }

  const processImage = async () => {
    if (!file) return
    setProcessing(true); setError(null); setResult(null)
    try {
      const res = await api.processImage(siteId, file)
      setResult(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Processing failed. Check the backend is on port 8001.')
    } finally { setProcessing(false) }
  }

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center gap-2">
        <Camera className="text-info" size={18} />
        <div>
          <h1 className="text-white font-black tracking-[0.15em] text-lg">COMPUTER VISION / DATASET BAY</h1>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">YOLO OBJECT DETECTION · FRAME ANALYSIS CONDUIT</div>
        </div>
      </div>

      {/* pipeline strip */}
      <div className="hazard-bar h-1.5 w-56 opacity-70"></div>
      <div className="tech-panel p-3 flex flex-wrap items-center gap-2 readout text-[10px] text-slate-400">
        {['DATASET / VIDEO', 'FRAME EXTRACT', 'YOLO DETECT', 'MONITORING EVENT', 'RISK AGENT'].map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            <span className="bg-[#0a0e13] border border-steel px-2 py-1">{s}</span>
            {i < 4 && <span className="text-hazard">›</span>}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        {/* Upload bay */}
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="bracket-label mb-3 flex items-center gap-1.5"><CloudCog size={12} /> INPUT HOPPER</div>

          <label className="flex flex-col items-center justify-center border-2 border-dashed border-steel bg-[#0a0e13] p-6 cursor-pointer hover:border-hazard transition group">
            <Upload className="text-slate-500 group-hover:text-hazard mb-2" size={26} />
            <span className="text-sm text-slate-300">Select construction site image</span>
            <span className="readout text-[10px] text-slate-500 mt-1">JPG / PNG — workers, excavators, equipment</span>
            <input type="file" accept="image/*" onChange={onFileChange} className="hidden" />
          </label>

          {preview && (
            <div className="mt-3">
              <img src={preview} alt="preview" className="rounded-[4px] max-h-60 object-contain w-full bg-[#080b0f] border border-steel" />
              <button onClick={processImage} disabled={processing}
                className="mt-3 w-full bg-hazard hover:bg-hazard-2 disabled:opacity-50 text-black readout text-[11px] font-bold tracking-wider py-2 flex items-center justify-center gap-2">
                {processing ? <><Spinner /> DETECTING OBJECTS...</> : <><Scan size={14} /> EXECUTE DETECTION</>}
              </button>
            </div>
          )}

          {error && <div className="mt-3 readout text-[11px] text-signal bg-signal/10 border border-signal/40 p-2">⚠ {error}</div>}
        </div>

        {/* Results bay */}
        <div className="lg:col-span-3 tech-panel p-4">
          <div className="bracket-label mb-3">DETECTION OUTPUT</div>

          {!preview && !result && (
            <div className="text-center py-16">
              <Camera className="mx-auto mb-3 text-slate-600" size={40} />
              <p className="text-sm text-slate-500">Load an image into the input hopper, then run detection.</p>
              <p className="readout text-[10px] text-slate-600 mt-1">OUTPUT FRAMES + OBJECTS WILL RENDER HERE</p>
            </div>
          )}

          {processing && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-400">
              <Loader2 className="animate-spin text-info" size={28} />
              <span className="readout text-[12px] tracking-widest">PROCESSING FRAME @ YOLOv8...</span>
            </div>
          )}

          {!processing && result && (
            <div className="space-y-3">
              {/* Overview stats */}
              <div className="grid grid-cols-3 gap-3">
                <StatChip icon={Users} label="Workers" value={result.worker_count}
                  accent="#4aa8ff" />
                <StatChip icon={Truck} label="Vehicles" value={result.vehicle_count}
                  accent="#f5a623" />
                <StatChip icon={Package} label="Objects" value={result.detections?.length || 0}
                  accent="#36d17e" />
              </div>

              {/* Action bar */}
              <ActionBar
                active={detail}
                onToggle={(k) => setDetail(detail === k ? null : k)}
                items={[
                  { key: 'list', label: 'Object List', icon: ListTree },
                  { key: 'raw', label: 'Raw JSON', icon: FileJson },
                ]}
              />

              {detail === 'list' && (
                <Section title="DETECTED OBJECT LIST" badge={`${result.detections?.length || 0} OBJECTS`} onClose={() => setDetail(null)}>
                  {result.detections?.length === 0 && <div className="readout text-[11px] text-slate-500">NO OBJECTS DETECTED — TRY A DIFFERENT FRAME</div>}
                  <div className="max-h-[320px] overflow-y-auto">
                    {result.detections?.map((d, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5 border-b border-steel/40 last:border-0 readout text-[12px]">
                        <div className="flex items-center gap-2">
                          <span className="led bg-info" /> <span className="text-slate-200 capitalize">{d.label}</span>
                        </div>
                        <div className="flex items-center gap-3 text-slate-500 text-[10px]">
                          <span>CONF {(d.confidence * 100).toFixed(0)}%</span><span>CLS {d.class_id}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {detail === 'raw' && (
                <Section title="RAW DETECTION OUTPUT" onClose={() => setDetail(null)}>
                  <button onClick={() => setShowRaw(!showRaw)}
                    className="flex items-center gap-1.5 readout text-[10px] text-slate-500 hover:text-white mb-2">
                    <FileJson size={12} /> {showRaw ? 'HIDE ' : 'VIEW '}FULL RESPONSE <ChevronDown size={12} className={showRaw ? 'rotate-180' : ''} />
                  </button>
                  {showRaw && (
                    <pre className="text-[10px] text-slate-400 bg-[#080b0f] border border-steel p-3 overflow-auto max-h-72">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  )}
                </Section>
              )}

              <div className="readout text-[10px] text-ok">EVENT LOGGED: {result.event_id.slice(0, 13)}… → QUEUED FOR SITE RISK AGENT</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
