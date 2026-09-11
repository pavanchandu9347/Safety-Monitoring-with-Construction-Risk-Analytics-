import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../services/api'

const AuthContext = createContext(null)

const TOKEN_KEY = 'buildsure_token'
const MANAGER_KEY = 'buildsure_manager'

export function AuthProvider({ children }) {
  const [manager, setManager] = useState(() => {
    try {
      const raw = localStorage.getItem(MANAGER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || null)
  const [loading, setLoading] = useState(true)

  // On first load, verify a stored token against the backend so a revoked or
  // expired session never leaves the operator inside the app.
  useEffect(() => {
    let cancelled = false
    const restore = async () => {
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const res = await api.getMe()
        if (!cancelled) {
          localStorage.setItem(MANAGER_KEY, JSON.stringify(res.data))
          setManager(res.data)
        }
      } catch {
        if (!cancelled) {
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem(MANAGER_KEY)
          setToken(null)
          setManager(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    restore()
    return () => { cancelled = true }
  }, [token])

  const login = useCallback(async (email, password) => {
    const res = await api.login(email, password)
    const { access_token, manager: m } = res.data
    localStorage.setItem(TOKEN_KEY, access_token)
    localStorage.setItem(MANAGER_KEY, JSON.stringify(m))
    setToken(access_token)
    setManager(m)
    return m
  }, [])

  const logout = useCallback(async () => {
    try {
      if (token) await api.logout()
    } catch {
      // Even if the server call fails, the local session must be cleared.
    }
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(MANAGER_KEY)
    setToken(null)
    setManager(null)
  }, [token])

  return (
    <AuthContext.Provider value={{ manager, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}