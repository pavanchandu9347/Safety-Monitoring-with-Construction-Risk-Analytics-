import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useSite } from '../hooks/useDashboard'
import { formatDate } from '../utils/risk'
import { Search, ShieldAlert, Filter, ListChecks, ShieldX, CheckCircle2, AlertTriangle } from 'lucide-react'
import { StatChip, Section, ActionBar } from '../components/progressive'

const STATUS = ['detected', 'investigating', 'mitigated', 'resolved']
const LEVEL_HEX = {
  LOW: '#36d17e', MEDIUM: '#f5a623', HIGH: '#ff7a3c', CRITICAL: '#ff5a3c',
}
const STATUS_HEX = {
  detected: '#ff5a3c', investigating: '#f5a623', mitigated: '#4aa8ff', resolved: '#36d17e',
}

export default function Hazards() {
  const siteId = useSite()
  const [hazards, setHazards] = useState([])
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [zone, setZone] = useState('')
  const [zones, setZones] = useState([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState('register')

  const load = async (filters = {}) => {
    setLoading(true)
    try {
      const params = {}
      if (filters.severity ?? severity) params.severity = filters.severity ?? severity
      if (filters.status ?? status) params.status = filters.status ?? status
      const res = await api.getHazards(siteId, params)
      let list = res.data
      const q = (filters.search !== undefined ? filters.search : search).toLowerCase()
      if (q) {
        list = list.filter((h) =>
          h.hazard_type.toLowerCase().includes(q) || h.description.toLowerCase().includes(q)
        )
      }
      setHazards(list)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [siteId])

  useEffect(() => {
    api.getZones(siteId).then((r) => setZones(r.data)).catch(() => {})
  }, [siteId])

  const applyFilters = (field, val) => {
    if (field === 'search') setSearch(val)
    if (field === 'severity') { setSeverity(val); load({ severity: val }) }
    if (field === 'status') { setStatus(val); load({ status: val }) }
    if (field === 'zone') setZone(val)
  }

  const updateStatus = async (id, newStatus) => {
    try { await api.updateHazardStatus(id, newStatus); load() } catch {}
  }

  const filtered = hazards.filter((h) => {
    if (zone && h.zone_id !== zone) return false
    if (search && !h.hazard_type.toLowerCase().includes(search.toLowerCase()) && !h.description.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      <div className="flex items-center gap-2">
        <ShieldAlert className="text-hazard" size={18} />
        <div>
          <h1 className="text-white font-black tracking-[0.15em] text-lg">HAZARD LOG</h1>
          <div className="readout text-[10px] text-slate-500 tracking-widest mt-0.5">DETECTED HAZARD REGISTER · CV + ENV + EQUIPMENT SOURCES</div>
        </div>
      </div>

      {/* Overview stat chips */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatChip icon={ListChecks} label="Total Registers" value={hazards.length} accent="#4aa8ff" />
        <StatChip icon={AlertTriangle} label="Open" value={hazards.filter((h) => h.status === 'detected' || h.status === 'investigating').length} accent="#f5a623" />
        <StatChip icon={ShieldX} label="Critical" value={hazards.filter((h) => h.severity === 'CRITICAL').length} accent="#ff5a3c" />
        <StatChip icon={CheckCircle2} label="Resolved" value={hazards.filter((h) => h.status === 'resolved').length} accent="#36d17e" />
      </div>

      {/* Filter bar */}
      <div className="hazard-bar h-1.5 w-40 opacity-70"></div>
      <div className="tech-panel p-3 flex flex-wrap items-center gap-3">
        <span className="readout text-[9px] text-slate-500 tracking-widest flex items-center gap-1"><Filter size={12} /> FILTER</span>
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
          <input value={search} onChange={(e) => applyFilters('search', e.target.value)} placeholder="SEARCH HAZARD / DESCRIPTION..."
            className="w-full bg-[#0a0e13] border border-steel readout text-[12px] text-white pl-8 pr-3 py-1.5 focus:outline-none focus:border-hazard" />
        </div>
        <div className="flex items-center gap-2 readout text-[11px]">
          {['severity', 'status', 'zone'].map((field) => {
            const val = field === 'severity' ? severity : field === 'status' ? status : zone
            const options = field === 'severity'
              ? ['', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
              : field === 'status' ? ['', ...STATUS] : ['', ...zones.map((z) => z.id)]
            return (
              <select key={field} value={val} onChange={(e) => applyFilters(field, e.target.value)}
                className="bg-[#0a0e13] border border-steel readout text-[11px] text-slate-200 px-2 py-1.5 focus:outline-none focus:border-hazard uppercase">
                <option value="">ALL {field.toUpperCase()}</option>
                {options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            )
          })}
        </div>
      </div>

      {/* Action bar */}
      <ActionBar
        active={detail}
        onToggle={(k) => setDetail(detail === k ? null : k)}
        items={[
          { key: 'register', label: 'Hazard Register', icon: ListChecks },
          { key: 'open', label: 'Open Only', icon: AlertTriangle },
          { key: 'critical', label: 'Critical', icon: ShieldX },
          { key: 'resolved', label: 'Resolved', icon: CheckCircle2 },
          { key: 'mitigation', label: 'Mitigations', icon: ShieldAlert },
        ]}
      />

      {loading && <div className="text-center readout text-slate-500 py-10">PARSING HAZARD REGISTER...</div>}
      {!loading && filtered.length === 0 && detail !== 'mitigation' && (
        <div className="tech-panel p-8 text-center readout text-sm text-slate-500">
          NO HAZARDS MATCH FILTERS — RUN RISK ANALYSIS TO GENERATE HAZARDS
        </div>
      )}

      {detail && !loading && (
        <Section title="HAZARD REGISTER" badge={`${filtered.length} RESULTS`} onClose={() => setDetail(null)}>
          <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
            {filtered
              .filter((h) => {
                if (detail === 'open') return h.status === 'detected' || h.status === 'investigating'
                if (detail === 'critical') return h.severity === 'CRITICAL'
                if (detail === 'resolved') return h.status === 'resolved'
                return true
              })
              .map((h) => {
                const hex = LEVEL_HEX[h.severity] || '#36d17e'
                const sHex = STATUS_HEX[h.status] || '#7e8c9c'
                return (
                  <div key={h.id} className="tech-panel p-3">
                    <div className="flex items-center justify-between gap-2 border-b border-steel pb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="readout text-[10px] font-bold px-1.5 py-0.5 tracking-wider" style={{ color: hex, border: `1px solid ${hex}` }}>{h.severity}</span>
                        <span className="readout text-[12px] font-bold text-white uppercase tracking-wide">{h.hazard_type.replace(/_/g, ' ')}</span>
                        <span className="readout text-[10px] text-slate-500">· {formatDate(h.timestamp)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="readout text-[9px] text-slate-500 tracking-widest uppercase">{h.source}</span>
                        <button onClick={() => updateStatus(h.id, h.status === 'detected' ? 'investigating' : h.status === 'investigating' ? 'mitigated' : h.status === 'mitigated' ? 'resolved' : 'detected')}
                          className="readout text-[10px] font-bold px-2 py-0.5 tracking-widest"
                          style={{ color: sHex, border: `1px solid ${sHex}` }}>
                          {h.status.toUpperCase()} ▸
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                      <div className="bg-[#0a0e13] border border-steel p-2.5">
                        <div className="readout text-[9px] text-slate-500 tracking-widest">EVIDENCE · {h.source}</div>
                        <div className="readout text-[12px] text-slate-300 italic mt-1">"{h.evidence}"</div>
                      </div>
                      <div className="bg-[#0a0e13] border border-ok/30 p-2.5">
                        <div className="readout text-[9px] text-ok tracking-widest">RECOMMENDED MITIGATION</div>
                        <div className="readout text-[12px] text-slate-300 mt-1">{h.recommended_mitigation}</div>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center gap-4 readout text-[10px] text-slate-500">
                      <span>ZONE: {h.zone_id || 'N/A'}</span>
                      <span>RISK CONTRIBUTION: +{h.risk_contribution.toFixed(1)}</span>
                    </div>
                  </div>
                )
              })}
          </div>
          {detail === 'mitigation' && filtered.length === 0 && (
            <div className="readout text-[11px] text-slate-500">NO HAZARDS — NOTHING TO MITIGATE</div>
          )}
        </Section>
      )}
    </div>
  )
}
