import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { ReportSections } from '../components/ReportSections'
import {
  FileText, RefreshCw, Download, FileCheck2, ChevronDown, ChevronRight,
  Loader2, AlertTriangle, ClipboardList,
} from 'lucide-react'

const fmtDate = (iso) => (iso ? String(iso).replace('T', ' ').slice(0, 19) : '—')

export default function Reports() {
  const siteId = useSite()
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [mode, setMode] = useState('structured') // structured | text
  const [msg, setMsg] = useState(null) // { type, text }
  const [hist, setHist] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.getReports(siteId)
      setReports(res.data.reports || [])
      setMsg(null)
    } catch {
      setMsg({ type: 'err', text: 'REPORTS UNAVAILABLE — CHECK THE BACKEND CONNECTION.' })
    } finally { setLoading(false) }
    api.getAnalyticsHistory(siteId).then((r) => setHist(r.data)).catch(() => setHist(null))
  }
  useEffect(() => { load() }, [siteId])

  const generate = async () => {
    setGenerating(true)
    setMsg(null)
    try {
      const r = await api.generateReport(siteId, {})
      setReports((prev) => [r.data, ...prev.filter((x) => x.id !== r.data.id)])
      setSelectedId(r.data.id)
      setMode('structured')
      setMsg({ type: 'ok', text: 'REPORT GENERATED FROM THE LATEST ANALYSIS EVIDENCE.' })
    } catch (e) {
      const detail = e?.response?.status === 404
        ? 'NO ANALYSIS EVIDENCE YET — RUN "ANALYZE SITE VIDEO" BEFORE GENERATING A REPORT.'
        : e?.response?.data?.detail || 'REPORT GENERATION FAILED — SEE BACKEND LOG.'
      setMsg({ type: 'err', text: detail })
    } finally { setGenerating(false) }
  }

  const download = async (report) => {
    setDownloading(true)
    try {
      const r = await api.getReportText(siteId, report.id)
      const blob = new Blob([r.data.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `buildsure-report-${report.id.slice(0, 12)}.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setMsg({ type: 'ok', text: 'REPORT TEXT DOWNLOADED (.TXT).' })
    } catch {
      setMsg({ type: 'err', text: 'DOWNLOAD FAILED — FULL TEXT UNAVAILABLE.' })
    } finally { setDownloading(false) }
  }

  const selected = reports.find((r) => r.id === selectedId) || null

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ClipboardList className="text-hazard" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">RISK REPORTS</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">
            EXECUTIVE REPORTS · BUILT ONLY FROM PERSISTED ANALYSIS EVIDENCE
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="flex items-center gap-2 border border-steel hover:bg-steel text-slate-200 readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            <RefreshCw size={13} className={loading ? 'animate-spin text-info' : ''} /> REFRESH
          </button>
          <button onClick={generate} disabled={generating}
            className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 disabled:opacity-40 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition">
            {generating ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />}
            {generating ? 'GENERATING REPORT...' : 'GENERATE REPORT'}
          </button>
        </div>
      </div>
      <div className="hazard-bar h-1.5 w-48 opacity-70"></div>

      {/* Status / error banner */}
      {msg && (
        <div className={`tech-panel p-3 border-l-2 ${msg.type === 'ok' ? 'border-l-ok' : 'border-l-signal'}`}>
          <p className={`readout text-[11px] font-bold flex items-center gap-2 ${msg.type === 'ok' ? 'text-ok' : 'text-signal'}`}>
            <AlertTriangle size={13} /> {msg.text}
          </p>
        </div>
      )}

      {loading && reports.length === 0 && (
        <div className="p-8 readout text-slate-400 text-center">LOADING REPORTS...</div>
      )}

      {!loading && reports.length === 0 && (
        <div className="tech-panel p-8 text-center readout text-sm text-slate-500">
          <FileText className="mx-auto mb-3 text-slate-600" size={40} />
          <div>NO REPORTS GENERATED YET</div>
          <div className="text-[10px] mt-1 text-slate-400">CLICK "GENERATE REPORT" TO BUILD ONE FROM THE LATEST REAL ANALYSIS — MISSING EVIDENCE IS MARKED NOT_AVAILABLE, NEVER FABRICATED</div>
        </div>
      )}

      {/* Report list */}
      {reports.length > 0 && (
        <div className="tech-panel p-4">
          <div className="bracket-label mb-3 flex items-center justify-between">
            <span>REPORT REGISTER</span>
            <span className="readout text-[9px] text-slate-500 tracking-widest">{reports.length} RECORDS</span>
          </div>
          <div className="space-y-1">
            {reports.map((r) => (
              <button key={r.id} onClick={() => { setSelectedId(selectedId === r.id ? null : r.id); setMode('structured') }}
                className="w-full text-left flex items-center justify-between gap-3 border border-steel bg-[#0a0e13] px-3 py-2.5 hover:bg-[#151b23] transition">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText size={14} className="text-info shrink-0" />
                  <div className="readout min-w-0">
                    <div className="text-[11px] text-slate-200 font-semibold truncate">{r.title || 'Risk Intelligence Report'}</div>
                    <div className="text-[9px] text-slate-500 truncate">{r.summary}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="readout text-[9px] px-1.5 py-0.5 border border-steel-2 text-slate-400 uppercase">
                    {r.status}
                  </span>
                  <span className="readout text-[9px] text-slate-500">
                    ANA {String(r.analysis_id || '').slice(0, 8) || '—'} · {r.created_at ? formatTime(r.created_at) : '—'}
                  </span>
                  {selectedId === r.id ? <ChevronDown size={13} className="text-hazard" /> : <ChevronRight size={13} className="text-slate-500" />}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Report viewer */}
      {selected && (
        <div className="space-y-3">
          <div className="tech-panel p-3 flex items-center justify-between flex-wrap gap-2">
            <div className="readout text-[11px] text-slate-300">
              {selected.title || 'Risk Intelligence Report'} · {fmtDate(selected.created_at)}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setMode('structured')}
                className={`readout text-[10px] font-bold tracking-wider px-2.5 py-1.5 border transition ${mode === 'structured' ? 'bg-hazard text-black border-hazard' : 'border-steel text-slate-200 hover:bg-steel'}`}>
                STRUCTURED
              </button>
              <button onClick={() => setMode('text')}
                className={`readout text-[10px] font-bold tracking-wider px-2.5 py-1.5 border transition ${mode === 'text' ? 'bg-hazard text-black border-hazard' : 'border-steel text-slate-200 hover:bg-steel'}`}>
                FULL TEXT
              </button>
              <button onClick={() => download(selected)} disabled={downloading}
                className="flex items-center gap-1.5 readout text-[10px] font-bold tracking-wider border border-info text-info hover:bg-info hover:text-black px-2.5 py-1.5 transition disabled:opacity-40">
                <Download size={12} /> {downloading ? 'DOWNLOADING...' : 'DOWNLOAD .TXT'}
              </button>
            </div>
          </div>

          {mode === 'structured' && <ReportSections report={selected} history={hist} />}

          {mode === 'text' && <FullText siteId={siteId} report={selected} />}
        </div>
      )}
    </div>
  )
}

function FullText({ siteId, report }) {
  const [text, setText] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true); setErr(null)
    api.getReportText(siteId, report.id)
      .then((r) => { if (active) setText(r.data.text) })
      .catch(() => { if (active) setErr('FULL TEXT UNAVAILABLE') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [siteId, report.id])

  if (err) return <div className="tech-panel p-4 readout text-signal text-[11px]">{err}</div>
  return (
    <div className="tech-panel p-4">
      {loading && <div className="readout text-slate-400 text-[11px] py-4 text-center">RENDERING FULL TEXT...</div>}
      {!loading && text && (
        <pre className="readout text-[10px] text-slate-300 whitespace-pre-wrap max-h-[640px] overflow-y-auto">{text}</pre>
      )}
    </div>
  )
}