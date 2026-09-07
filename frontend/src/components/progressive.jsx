import { X } from 'lucide-react'

/* Compact key-metric chip used in every module's overview row. */
export function StatChip({ icon: Icon, label, value, accent, sub }) {
  return (
    <div className="tech-panel p-4 flex items-center gap-3">
      <div className="w-9 h-9 shrink-0 rounded-[4px] border border-steel bg-panel-3 flex items-center justify-center"
        style={{ color: accent }}>
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <div className="readout text-2xl font-black text-white tabular-nums leading-none">{value}</div>
        <div className="readout text-[9px] text-slate-500 tracking-widest mt-1 uppercase truncate">{label}</div>
        {sub && <div className="readout text-[9px] text-slate-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

/* Progressive-disclosure detail panel, shown only after its action button is pressed. */
export function Section({ title, badge, onClose, children }) {
  return (
    <div className="tech-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="bracket-label flex items-center gap-2">
          {title}
          {badge != null && <span className="readout text-[9px] text-slate-500 tracking-widest">· {badge}</span>}
        </span>
        <button onClick={onClose} className="readout text-[10px] text-slate-500 hover:text-white flex items-center gap-1">
          <X size={11} /> CLOSE
        </button>
      </div>
      {children}
    </div>
  )
}

/* Action bar of buttons; each toggles a named detail panel in place. */
export function ActionBar({ items, active, onToggle }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
      {items.map(({ key, label, icon: Icon }) => (
        <button key={key} onClick={() => onToggle(key)}
          className={`flex items-center justify-center gap-2 readout text-[11px] font-bold tracking-wider px-3 py-3 transition border ${
            active === key
              ? 'bg-hazard text-black border-hazard'
              : 'bg-panel-3 border border-steel-2 text-slate-200 hover:bg-steel hover:text-white'
          }`}>
          <Icon size={13} /> {label.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
