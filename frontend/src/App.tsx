import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import CVPage from './pages/CVPage'
import CVDetail from './pages/CVDetail'
import AnalysisDetail from './pages/AnalysisDetail'
import ApplicationsPage from './pages/ApplicationsPage'
import ApplicationDetail from './pages/ApplicationDetail'
import MarketPage from './pages/MarketPage'
import Attivita from './pages/Attivita'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/"                                   element={<Dashboard />} />
        <Route path="/cv"                                 element={<CVPage />} />
        <Route path="/cv/:id"                             element={<CVDetail />} />
        <Route path="/cv/:id/analysis/:analysisId"        element={<AnalysisDetail />} />
        <Route path="/attivita"                           element={<Attivita />} />
        <Route path="/applications"                       element={<ApplicationsPage />} />
        <Route path="/applications/:id"                   element={<ApplicationDetail />} />
        <Route path="/market"                             element={<MarketPage />} />
      </Route>
    </Routes>
  )
}
