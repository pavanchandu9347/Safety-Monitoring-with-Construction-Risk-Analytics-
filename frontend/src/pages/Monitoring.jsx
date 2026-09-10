import { useState, useEffect, useRef } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { Radio, Play, Activity, Wind, Thermometer, Wrench, Rss, ShieldAlert, Loader2 } from 'lucide-react'
import { StatChip, Section, ActionBar } from '../components/progressive'

export default function Monitoring() {
  const siteId = useSite()
  const [events, setEvents] = useState([])
  const [equipment, setEquipment] = useState([])
  const [latest, setLatest] = useState(null)
  const [running, setRunning] = useState(false)
  const [detail, setDetail] = useState(null)
  const feedRef = useRef(null)

  const load = async () => {
    const [evRes, eqRes, envRes, latestRes] = await Promise.allSettled([
      api.getMonitoring(siteId),
      api.getEquipmentDemo(),
      api.getEnvironmentalDemo('excavation'),
      api.getLatestVideoAnalysis(siteId),
    ])
    if (evRes.status === 'fulfilled') setEvents(evRes.value.data || [])
    if (eqRes.status === 'fulfilled') setEquipment(eqRes.value.data?.equipment || [])
    if (latestRes.status === 'fulfilled' && latestRes.value.data?.status === 'completed') {
      setLatest(latestRes.value.data)
    }
  }
  useEffect(() => { load() }, [siteId])
  useEffect(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight }, [events])

  const runAnalysis = async () => {
    setRunning(true)
    try { await api.analyzeVideo(siteId); await load() } finally { setRunning(false) }
  }

  // Environmental cells come from the latest REAL video analysis. Every value
  // here is derived from actual frame evidence; dimensions the video cannot
  // support (weather/temp/wind/ground) are shown as "Unavailable", never
  // fabricated.
  const envCells = latest?.video ? {
    'LIGHTING': latest.video.lighting_condition || 'Unavailable',
    'FRAMES': `${latest.video.frames_analyzed ?? 0} @ ${latest.video.frame_interval ?? 0}f`,
    'WORKERS': `${latest.worker_count ?? 0} DETECTED`,
    'VEHICLES': `${latest.vehicle_count ?? 0} DETECTED`,
    'WEATHER': 'Unavailable',
    'TEMP': 'Unavailable',
    'WIND': 'Unavailable',
    'GROUND': 'Unavailable',
  } : {}

  const envList = Object.entries(envCells)

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="text-info" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">SENSOR MONITORING FEED</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">VIDEO-DERIVED ENVIRONMENTAL + EQUIPMENT TELEMETRY</div>
        </div>
        <button onClick={runAnalysis} disabled={running}
          className="flex items-center gap-2 bg-hazard hover:bg-hazard-2 text-black readout text-[11px] font-bold tracking-wider px-3 py-2 transition disabled:opacity-50">
          {running ? <><Loader2 size={13} className="animate-spin" /> ANALYZING VIDEO...</> : <><Play size={13} /> ANALYZE SITE VIDEO</>}
        </button>
      </div>

      <div className="hazard-bar h-1.5 w-40 opacity-70"></div>

      {/* Overview stat chips */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatChip icon={Rss} label="Events Streamed" value={events.length} accent="#4aa8ff" />
        <StatChip icon={Wrench} label="Equipment Assets" value={equipment.length} accent="#f5a623"
          sub={`${equipment.filter((e) => e.status === 'active').length} active`} />
        <StatChip icon={Thermometer} label="Workers" value={latest?.worker_count ?? '—'} accent="#36d17e" sub="yolo persons" />
        <StatChip icon={Wind} label="Vehicles" value={latest?.vehicle_count ?? '—'} accent="#b794ff" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Feed console (primary, always visible) */}
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="bracket-label mb-3 flex items-center justify-between">
            <span>LIVE DATA CONSOLE</span>
            <span className="flex items-center gap-1.5 text-ok"><span className="led led-on bg-ok" /> LINKED TO ANALYSIS</span>
          </div>
          <div ref={feedRef} className="max-h-[540px] overflow-y-auto font-mono space-y-0.5 bg-[#080b0f] border border-steel">
            {events.length === 0 && (
              <div className="p-6 text-slate-500 text-center text-sm">NO EVENTS IN BUFFER — RUN "ANALYZE SITE VIDEO" TO EMIT SENSOR EVENTS</div>
            )}
            {events.map((e, i) => (
              <div key={e.id || i} className="flex items-start gap-3 px-3 py-1.5 border-b border-steel/30 hover:bg-[#0e1319]">
                <span className="text-slate-400 text-[11px] whitespace-nowrap select-none">{formatTime(e.timestamp)}</span>
                <span className="text-ok text-[11px] mt-px">›</span>
                <div className="text-[11px]">
                  <span className="text-info font-semibold uppercase tracking-wide mr-2">{e.event_type.replace(/_/g, ' ')}</span>
                  <span className="text-slate-300">{e.description}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Action bar for detail telemetry */}
          <div className="mt-3">
            <ActionBar
              active={detail}
              onToggle={(k) => setDetail(detail === k ? null : k)}
              items={[
                { key: 'env', label: 'Environmental', icon: Wind },
                { key: 'equipment', label: 'Equipment', icon: Wrench },
                { key: 'summary', label: 'Feed Summary', icon: ShieldAlert },
              ]}
            />
          </div>
        </div>

        {/* Detail telemetry (progressive disclosure) */}
        <div className="space-y-3">
          {detail === 'env' && (
            <Section title="ENVIRONMENTAL MONITOR" badge="VIDEO" onClose={() => setDetail(null)}>
              {envList.length ? (
                <div className="grid grid-cols-2 gap-2">
                  {envList.map(([k, v]) => (
                    <div key={k} className="bg-[#0a0e13] border border-steel px-2.5 py-2">
                      <div className="readout text-[8px] text-slate-500 tracking-widest">{k}</div>
                      <div className="readout text-[13px] text-slate-100 font-semibold truncate">{v || '—'}</div>
                    </div>
                  ))}
                </div>
              ) : <div className="readout text-xs text-slate-500">NO DATA — ANALYZE A VIDEO FIRST</div>}
            </Section>
          )}

          {detail === 'equipment' && (
            <Section title="EQUIPMENT STATE" badge="VIDEO" onClose={() => setDetail(null)}>
              {equipment.length === 0 && <div className="readout text-xs text-slate-500">NO EQUIPMENT — ANALYZE A VIDEO FIRST</div>}
              {equipment.map((eq) => (
                <div key={eq.name} className="flex items-center justify-between py-1.5 border-b border-steel/50 last:border-0">
                  <div className="readout">
                    <div className="text-[12px] text-slate-200">{eq.name}</div>
                    <div className="text-[8px] text-slate-500 tracking-widest uppercase">{eq.activity}</div>
                  </div>
                  <span className="readout text-[9px] px-1.5 py-0.5"
                    style={eq.status === 'active' ? { color: '#36d17e', border: '1px solid #36d17e' }
                      : eq.status === 'maintenance' ? { color: '#f5a623', border: '1px solid #f5a623' }
                      : { color: '#7e8c9c', border: '1px solid #2a3542' }}>{eq.status.toUpperCase()}</span>
                </div>
              ))}
            </Section>
          )}

          {detail === 'summary' && (
            <Section title="FEED SUMMARY" onClose={() => setDetail(null)}>
              <div className="space-y-1.5">
                <div className="flex justify-between readout text-[11px] text-slate-300"><span>Events Streamed</span><span className="text-white">{events.length}</span></div>
                <div className="flex justify-between readout text-[11px] text-slate-300"><span>Equipment Assets</span><span className="text-ok">{equipment.length}</span></div>
                <div className="flex justify-between readout text-[11px] text-slate-300"><span>Active Units</span><span className="text-hazard">{equipment.filter((e) => e.status === 'active').length}</span></div>
                <div className="flex justify-between readout text-[11px] text-slate-300"><span>Lighting</span><span className="text-white uppercase">{latest?.video?.lighting_condition || '—'}</span></div>
              </div>
            </Section>
          )}

          {!detail && (
            <div className="tech-panel p-4 text-center">
              <Activity className="mx-auto mb-2 text-slate-400" size={26} />
              <p className="readout text-[10px] text-slate-500 tracking-widest">SELECT A TELEMETRY VIEW ABOVE FOR DETAILED READOUT</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}