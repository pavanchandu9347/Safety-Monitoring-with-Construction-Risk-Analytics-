import { Routes, Route } from 'react-router-dom'
import Layout from './layouts/Layout'
import Dashboard from './pages/Dashboard'
import Monitoring from './pages/Monitoring'
import Video from './pages/Video'
import Hazards from './pages/Hazards'
import Analysis from './pages/Analysis'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/video" element={<Video />} />
        <Route path="/hazards" element={<Hazards />} />
        <Route path="/analysis" element={<Analysis />} />
      </Route>
    </Routes>
  )
}
