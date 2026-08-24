import { useCallback, useEffect, useState } from 'react'
import { Gauge, RadioTower } from 'lucide-react'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import CitizenReportModal from './components/CitizenReportModal'
import DashboardPage from './pages/DashboardPage'
import RiskMapPage from './pages/RiskMapPage'
import WarningsPage from './pages/WarningsPage'
import RoadRiskPage from './pages/RoadRiskPage'
import CitizenReportsPage from './pages/CitizenReportsPage'
import SystemStatusPage from './pages/SystemStatusPage'
import api from './services/api'

const labels = {
  en: { title: 'AI-Based Landslide Early Warning & Risk Monitoring', pilot: 'Pilot', systemStatus: 'System Status', language: 'Language', dashboard: 'Dashboard', riskMap: 'Risk Map', citizenReport: 'Citizen Report' },
  hi: { title: 'AI आधारित भूस्खलन पूर्व चेतावनी एवं जोखिम निगरानी', pilot: 'पायलट', systemStatus: 'सिस्टम स्थिति', language: 'भाषा', dashboard: 'डैशबोर्ड', riskMap: 'जोखिम मानचित्र', citizenReport: 'नागरिक रिपोर्ट' },
}

const validRoutes = new Set(['/dashboard', '/risk-map', '/warnings', '/road-risk', '/citizen-reports', '/system-status'])

const getRouteFromHash = () => {
  const hashRoute = window.location.hash.replace(/^#/, '')
  return validRoutes.has(hashRoute) ? hashRoute : '/dashboard'
}

export default function App() {
  const [data, setData] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [language, setLanguage] = useState('en')
  const [reportOpen, setReportOpen] = useState(false)
  const [acknowledged, setAcknowledged] = useState([])
  const [route, setRoute] = useState(getRouteFromHash)
  const [loadError, setLoadError] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoadError(false)
    api.getDashboard()
      .then((dashboard) => {
        if (!active) return
        const highestRiskCell = dashboard.riskCells.reduce((highest, cell) =>
          cell.final_risk_score > highest.final_risk_score ? cell : highest
        )
        setData(dashboard)
        setSelectedCell(highestRiskCell)
      })
      .catch(() => {
        if (!active) return
        setData(null)
        setLoadError(true)
      })
    return () => { active = false }
  }, [loadAttempt])

  useEffect(() => {
    const syncRoute = () => {
      const nextRoute = getRouteFromHash()
      if (window.location.hash !== '#' + nextRoute) {
        window.history.replaceState(null, '', '#' + nextRoute)
      }
      setRoute(nextRoute)
      window.requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: 'auto' }))
    }

    syncRoute()
    window.addEventListener('hashchange', syncRoute)
    return () => window.removeEventListener('hashchange', syncRoute)
  }, [])

  const closeReport = useCallback(() => setReportOpen(false), [])

  const navigate = useCallback((nextRoute) => {
    const nextHash = '#' + nextRoute
    if (window.location.hash === nextHash) {
      setRoute(nextRoute)
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
      return
    }
    window.location.hash = nextHash
  }, [])

  const viewAlertOnMap = (cellId) => {
    const cell = data.riskCells.find((item) => item.cell_id === cellId)
    if (cell) setSelectedCell(cell)
    navigate('/risk-map')
  }

  if (loadError) {
    return <main className="loading-screen" role="alert"><div className="loading-mark"><Gauge size={26} /></div><strong>Historical replay data could not be loaded</strong><span>Check the replay artifacts and try again.</span><button className="button-primary" type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>Retry</button></main>
  }

  if (!data) {
    return <main className="loading-screen"><div className="loading-mark"><Gauge size={26} /></div><strong>Preparing risk monitoring console</strong><span>Loading historical replay data…</span></main>
  }

  const mapProps = {
    riskGeoJson: data.riskGeoJson,
    roadGeoJson: data.roadGeoJson,
    settlementGeoJson: data.settlementGeoJson,
    historicalLandslides: data.historicalLandslides,
    boundaryGeoJson: data.sikkimBoundary,
    selectedCell,
    onSelectCell: setSelectedCell,
  }

  const renderRoute = () => {
    switch (route) {
      case '/risk-map':
        return <RiskMapPage mapProps={mapProps} selectedCell={selectedCell} />
      case '/warnings':
        return <WarningsPage alerts={data.alerts} priorities={data.emergencyPriorities} priorityCounts={data.meta.priority_counts} acknowledged={acknowledged} onAcknowledge={(id) => setAcknowledged((current) => [...current, id])} onView={viewAlertOnMap} />
      case '/road-risk':
        return <RoadRiskPage roads={data.roads} exposureSummary={data.exposureSummary} />
      case '/citizen-reports':
        return <CitizenReportsPage onOpenReport={() => setReportOpen(true)} />
      case '/system-status':
        return <SystemStatusPage data={data} language={language} onLanguageChange={setLanguage} />
      default:
        return (
          <DashboardPage
            data={data}
            mapProps={mapProps}
            selectedCell={selectedCell}
            acknowledged={acknowledged}
            onAcknowledge={(id) => setAcknowledged((current) => [...current, id])}
            onViewAlert={viewAlertOnMap}
            onViewAllWarnings={() => navigate('/warnings')}
          />
        )
    }
  }

  return (
    <div className="app app-shell">
      <Sidebar currentRoute={route} />
      <div className="app-workspace">
        <Header meta={data.meta} labels={labels[language]} />
        <main className="main-content route-workspace" key={route}>
          <div className="demo-notice"><RadioTower size={16} /><p><strong>Historical Replay · 19 Oct 2021.</strong> Real model risk combined with real OSM vehicular-road and named-settlement exposure.</p><span>NOT LIVE</span></div>
          {renderRoute()}
        </main>
        <footer><strong>SIH26001 · Sikkim Pilot</strong><span>HISTORICAL REPLAY · 19 OCT 2021</span></footer>
      </div>
      <CitizenReportModal open={reportOpen} onClose={closeReport} />
    </div>
  )
}
