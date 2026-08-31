import { useState, useEffect, useRef } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatTime } from '../utils/risk'
import { Radio, Play, Activity, Wind } from 'lucide-react'

export default function Monitoring() {
  const siteId = useSite()
  const [events, setEvents] = useState([])
  const [equipment, setEquipment] = useState([])
  const [environmental, setEnvironmental] = useState(null)
  const [simulating, setSimulating] = useState(false)
  const feedRef = useRef(null)

  const load = async () => {
    try {
      const [evRes, eqRes, envRes] = await Promise.all([
        api.getMonitoring(siteId),
        api.getEquipmentDemo(),
        api.getEnvironmentalDemo('excavation'),
      ])
      setEvents((prev) => (prev.length ? prev : evRes.data))
      setEquipment(eqRes.data)
      setEnvironmental(envRes.data)
    } catch {}
  }
  useEffect(() => { load() }, [siteId])
  useEffect(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight }, [events])

  const runSimulate = async () => {
    setSimulating(true)
    try {
      const res = await api.simulateMonitoring(siteId)
      const env0 = Object.values(res.data.environmental_data || {})[0]
      const active = res.data.equipment_data.filter((e) => e.status === 'active').length
      const now = new Date().toISOString()
      setEvents((prev) => [{
        id: 'evt_' + Date.now(), timestamp: now,
        event_type: 'simulated_monitoring',
        description: `SENSOR PACK · ${env0?.weather || '—'} / VIS ${env0?.visibility || '—'} · ${active} ACTIVE UNITS`,
        source: 'demo_simulation',
      }, ...prev])
    } finally { setSimulating(false) }
  }

  const envCells = environmental ? [
    ['TEMP', `${environmental.temperature_celsius}°C`],
    ['HUMID', `${environmental.humidity_percent}%`],
    ['WIND', `${environmental.wind_speed_kmh} KM/H`],
    ['WEATHER', environmental.weather.toUpperCase()],
    ['VISIBILITY', environmental.visibility.toUpperCase()],
    ['GROUND', (environmental.ground_condition || '').toUpperCase()],
    ['LIGHTING', (environmental.lighting_condition || '').toUpperCase()],
    ['SCNR.', (environmental.scenario || '').toUpperCase()],
  ] : []

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="text-info" size={18} />
            <h1 className="text-white font-black tracking-[0.15em] text-lg">SENSOR MONITORING FEED</h1>
          </div>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">ENVIRONMENTAL + EQUIPMENT TELEMETRY · SIMULATED SOURCE</div>
        </div>
        <button onClick={runSimulate} disabled={simulating}
          className="flex items-center gap-2 bg-steel-2 hover:bg-steel text-white readout text-[11px] font-bold tracking-wider px-3 py-2 transition disabled:opacity-50">
          {simulating ? <><Activity size={13} /> INGESTING...</> : <><Play size={13} /> SIMULATE NEXT TICK</>}
        </button>
      </div>

      <div className="hazard-bar h-1.5 w-40 opacity-70"></div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Feed console */}
        <div className="lg:col-span-2 tech-panel p-4">
          <div className="bracket-label mb-3 flex items-center justify-between">
            <span>LIVE DATA CONSOLE</span>
            <span className="flex items-center gap-1.5 text-ok"><span className="led led-on bg-ok" /> STREAMING</span>
          </div>
          <div ref={feedRef} className="max-h-[540px] overflow-y-auto font-mono space-y-0.5 bg-[#080b0f] border border-steel">
            {events.length === 0 && (
              <div className="p-6 text-slate-500 text-center text-sm">NO EVENTS IN BUFFER — CLICK "SIMULATE NEXT TICK" TO STREAM DATA</div>
            )}
            {events.map((e, i) => (
              <div key={e.id || i} className="flex items-start gap-3 px-3 py-1.5 border-b border-steel/30 hover:bg-[#0e1319]">
                <span className="text-slate-600 text-[11px] whitespace-nowrap select-none">{formatTime(e.timestamp)}</span>
                <span className="text-ok text-[11px] mt-px">›</span>
                <div className="text-[11px]">
                  <span className="text-info font-semibold uppercase tracking-wide mr-2">{e.event_type.replace(/_/g, ' ')}</span>
                  <span className="text-slate-300">{e.description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          {/* Environmental readout panel */}
          <div className="tech-panel p-4">
            <div className="bracket-label mb-2 flex items-center gap-1.5"><Wind size={12} /> ENV. MONITOR <span className="text-slate-600">· SIM</span></div>
            {environmental ? (
              <div className="grid grid-cols-2 gap-2">
                {envCells.map(([k, v]) => (
                  <div key={k} className="bg-[#0a0e13] border border-steel px-2.5 py-2">
                    <div className="readout text-[8px] text-slate-500 tracking-widest">{k}</div>
                    <div className="readout text-[13px] text-slate-100 font-semibold truncate">{v}</div>
                  </div>
                ))}
              </div>
            ) : <div className="readout text-xs text-slate-500">NO DATA</div>}
          </div>

          {/* Equipment telemetry */}
          <div className="tech-panel p-4">
            <div className="bracket-label mb-2">EQUIPMENT STATE <span className="text-slate-600">· SIM</span></div>
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
          </div>
        </div>
      </div>
    </div>
  )
}
