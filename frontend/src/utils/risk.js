export const RISK_COLORS = {
  LOW: { text: 'text-emerald-400', bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', hex: '#22c55e', solid: 'bg-emerald-500' },
  MEDIUM: { text: 'text-amber-400', bg: 'bg-amber-500/15', border: 'border-amber-500/40', hex: '#f59e0b', solid: 'bg-amber-500' },
  HIGH: { text: 'text-red-400', bg: 'bg-red-500/15', border: 'border-red-500/40', hex: '#ef4444', solid: 'bg-red-500' },
  CRITICAL: { text: 'text-red-600', bg: 'bg-red-700/20', border: 'border-red-700/50', hex: '#b91c1c', solid: 'bg-red-700' },
}

export const SEVERITY_RANK = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 }

export function getRiskColor(level) {
  return RISK_COLORS[level] || RISK_COLORS.LOW
}

export function riskLevelFromScore(score) {
  if (score < 25) return 'LOW'
  if (score < 50) return 'MEDIUM'
  if (score < 75) return 'HIGH'
  return 'CRITICAL'
}

export function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
