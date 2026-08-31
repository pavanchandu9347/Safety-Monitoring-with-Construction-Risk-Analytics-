import { useEffect, useState } from 'react'
import { api } from '../services/api'

const SITE_ID = 'site_riverside_main'

export function useDashboard(refreshMs = 10000) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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

  return { data, loading, error, reload: () => load() }
}

export function useSite() {
  return SITE_ID
}
