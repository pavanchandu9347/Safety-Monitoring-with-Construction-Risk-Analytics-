import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './layouts/Layout'
import Dashboard from './pages/Dashboard'
import Monitoring from './pages/Monitoring'
import Video from './pages/Video'
import Hazards from './pages/Hazards'
import Analysis from './pages/Analysis'
import Safety from './pages/Safety'
import Compliance from './pages/Compliance'
import Insurance from './pages/Insurance'
import Intelligence from './pages/Intelligence'
import Reports from './pages/Reports'
import Login from './pages/Login'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Loader2 } from 'lucide-react'

function ProtectedLayout() {
  const { manager, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0b0f14]">
        <Loader2 className="animate-spin text-hazard" size={28} />
      </div>
    )
  }
  if (!manager) return <Navigate to="/login" replace />
  return <Layout />
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/video" element={<Video />} />
          <Route path="/hazards" element={<Hazards />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/safety" element={<Safety />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/insurance" element={<Insurance />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/reports" element={<Reports />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App