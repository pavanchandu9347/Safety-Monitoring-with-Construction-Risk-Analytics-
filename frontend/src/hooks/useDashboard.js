import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

const SITE_ID = 'site_riverside_main'

// Map live risk_level back onto the existing threshold mapping is not needed:
// the backend already returns LOW/MEDIUM/HIGH/CRITICAL.

export function useDashboard(refreshMs = 10000) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Live-analysis state (from the backend's real YOLO pipeline over WebSocket).
  const [live, setLive] = useState({
    status: 'STOPPED',          // STOPPED | STARTING | LIVE | RECONNECTING | STREAM_ENDED | ERROR
    detail: '',
    workers: 0,
    risk_score: 0,
    risk_level: 'LOW',
    violations: 0,
    compliance: 0,
    reasons: [],
    events: [],
    last_detection: null,
  })
  const [liveTrend, setLiveTrend] = useState([])

  // Refs for the socket + backoff (avoids stale closures / duplicate loops).
  const wsRef = useRef(null)
  const backoffRef = useRef(1000)
  const aliveRef = useRef(true)

  const applySnapshot = (snap) => {
    if (!snap || typeof snap !== 'object') return
    const isMetrics = snap.type === 'metrics' || snap.status

    setLive((prev) => ({
      ...prev,
      status: snap.status || prev.status,
      detail: snap.detail || prev.detail,
      workers: snap.workers ?? prev.workers,
      risk_score: snap.risk_score ?? prev.risk_score,
      risk_level: snap.risk_level || prev.risk_level,
      violations: snap.total_violations ?? snap.violations ?? prev.violations,
      compliance: snap.ppe_compliance ?? prev.compliance,
      reasons: snap.reasons || prev.reasons,
      events: snap.events?.length ? snap.events : prev.events,
      last_detection: snap.last_detection || prev.last_detection,
    }))

    // Merge real detection-derived risk into the dashboard data so the
    // existing cards/charts re-render with genuine live values.
    if (isMetrics && (snap.risk_score != null || snap.risk_level)) {
      setData((prevData) => {
        if (!prevData) return prevData
        const current = prevData.current_risk_assessment || {}
        const updated = {
          ...prevData,
          current_risk_assessment: {
            ...current,
            overall_score: snap.risk_score ?? current.overall_score,
            risk_level: snap.risk_level || current.risk_level,
            summary: snap.reasons?.length ? snap.reasons.join(' · ') : current.summary,
          },
        }
        return updated
      })

      if (snap.risk_score != null && snap.timestamp) {
        setLiveTrend((prevTrend) => {
          const next = [
            ...prevTrend,
            { timestamp: snap.timestamp, score: snap.risk_score, risk_level: snap.risk_level || 'LOW' },
          ]
          return next.slice(-40)
        })
      }
    }
  }

  const connect = () => {
    if (!aliveRef.current) return
    const ws = new WebSocket(api.liveWsUrl(SITE_ID))
    wsRef.current = ws

    ws.onopen = () => {
      backoffRef.current = 1000
      setLive((p) => ({ ...p, status: p.status === 'STOPPED' ? 'STOPPED' : p.status }))
    }
    ws.onmessage = (e) => {
      if (e.data === '__pong__') return
      try { applySnapshot(JSON.parse(e.data)) } catch { /* ignore malformed */ }
    }
    ws.onclose = () => {
      if (!aliveRef.current) return
      setLive((p) => ({ ...p, status: 'RECONNECTING' }))
      const delay = backoffRef.current
      backoffRef.current = Math.min(backoffRef.current * 1.5, 10000)
      setTimeout(() => { if (aliveRef.current) connect() }, delay)
    }
    ws.onerror = () => { try { ws.close() } catch { /* noop */ } }
  }

  const load = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await api.getDashboard(SITE_ID)
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message || 'Failed to load dashboard')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(() => load(true), refreshMs)
    return () => clearInterval(id)
  }, [refreshMs])

  // One WebSocket connection, reconnecting, cleaned up on unmount.
  useEffect(() => {
    aliveRef.current = true
    connect()
    return () => {
      aliveRef.current = false
      if (wsRef.current) { try { wsRef.current.close() } catch { /* noop */ } }
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // REST fallback poll of live/status so the live panel still updates even when
  // the WebSocket connection is unavailable (e.g. a WS-less server/backend).
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await api.getLiveStatus(SITE_ID)
        applySnapshot(res.data)
      } catch { /* WS or next poll will pick up */ }
    }
    poll()
    const id = setInterval(poll, 4000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startLive = async () => {
    setLive((p) => ({ ...p, status: 'STARTING' }))
    try {
      const res = await api.startLive(SITE_ID)
      setLive((p) => ({ ...p, status: res.data?.status || p.status, detail: res.data?.detail || '' }))
    } catch (e) {
      setLive((p) => ({ ...p, status: 'ERROR', detail: e.response?.data?.detail || e.message }))
    }
  }

  const stopLive = async () => {
    try {
      const res = await api.stopLive(SITE_ID)
      setLive((p) => ({ ...p, status: res.data?.status || 'STOPPED', detail: res.data?.detail || '' }))
    } catch (e) {
      setLive((p) => ({ ...p, status: 'ERROR', detail: e.response?.data?.detail || e.message }))
    }
  }

  return {
    data,
    loading,
    error,
    reload: () => load(),
    live,
    liveTrend,
    startLive,
    stopLive,
  }
}

export function useSite() {
  return SITE_ID
}
