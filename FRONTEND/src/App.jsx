import { useCallback, useEffect, useState } from 'react'
import { Camera, ChevronRight, Gauge, RadioTower } from 'lucide-react'
import Header from './components/Header'
import SummaryCards from './components/SummaryCards'
import RiskMap from './components/RiskMap'
import SelectedCellPanel from './components/SelectedCellPanel'
import WeatherRiskPanel from './components/WeatherRiskPanel'
import RoadRiskPanel from './components/RoadRiskPanel'
import EmergencyPriorityPanel from './components/EmergencyPriorityPanel'
import AlertsPanel from './components/AlertsPanel'
import DataSourceStatus from './components/DataSourceStatus'
import CitizenReportModal from './components/CitizenReportModal'
import api from './services/api'

const labels = {
  en: { title: 'AI-Based Landslide Early Warning & Risk Monitoring', pilot: 'Pilot', systemStatus: 'System Status', language: 'Language', dashboard: 'Dashboard', riskMap: 'Risk Map', citizenReport: 'Citizen Report' },
  hi: { title: 'AI आधारित भूस्खलन पूर्व चेतावनी एवं जोखिम निगरानी', pilot: 'पायलट', systemStatus: 'सिस्टम स्थिति', language: 'भाषा', dashboard: 'डैशबोर्ड', riskMap: 'जोखिम मानचित्र', citizenReport: 'नागरिक रिपोर्ट' },
}

export default function App() {
  const [data, setData] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [language, setLanguage] = useState('en')
  const [reportOpen, setReportOpen] = useState(false)
  const [acknowledged, setAcknowledged] = useState([])

  useEffect(() => {
    api.getDashboard().then((dashboard) => {
      setData(dashboard)
      setSelectedCell(dashboard.riskCells[0])
    })
  }, [])

  const closeReport = useCallback(() => setReportOpen(false), [])

  const viewAlertOnMap = (cellId) => {
    const cell = data.riskCells.find((item) => item.cell_id === cellId)
    if (cell) setSelectedCell(cell)
    document.getElementById('risk-map')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (!data) {
    return <main className="loading-screen"><div className="loading-mark"><Gauge size={26} /></div><strong>Preparing risk monitoring console</strong><span>Loading demonstration data…</span></main>
  }

  return (
    <div className="app">
      <Header meta={data.meta} language={language} onLanguageChange={setLanguage} labels={labels[language]} />
      <main className="main-content" id="dashboard">
        <div className="demo-notice" style={{ background: '#0a3d46', borderColor: '#19717e' }}>
          <RadioTower size={17} style={{ color: '#26d0ce' }} />
          <p><strong>Operational Early Warning Mode.</strong> Real ML Model Active: Layer 1 Static Susceptibility (Roy et al. 2025) &amp; Layer 2 Dynamic Rainfall Trigger (NASA LHASA 2.0).</p>
          <span style={{ background: '#138b9c', color: '#fff' }}>ML LAYER 1 &amp; 2 ACTIVE</span>
        </div>
        <SummaryCards summary={data.meta.summary} />
        <div className="primary-grid">
          <RiskMap riskCells={data.riskCells} roads={data.roads} settlements={data.settlements} historicalLandslides={data.historicalLandslides} boundaryGeoJson={data.sikkimBoundary} selectedCell={selectedCell} onSelectCell={setSelectedCell} />
          <SelectedCellPanel cell={selectedCell} />
        </div>
        <div className="analysis-grid">
          <WeatherRiskPanel weather={data.weather} />
          <AlertsPanel alerts={data.alerts} acknowledged={acknowledged} onAcknowledge={(id) => setAcknowledged((current) => [...current, id])} onView={viewAlertOnMap} />
        </div>
        <RoadRiskPanel roads={data.roads} />
        <div className="operations-grid">
          <EmergencyPriorityPanel priorities={data.emergencyPriorities} />
          <div className="support-column">
            <DataSourceStatus sources={data.dataSources} />
            <section className="panel citizen-card" id="citizen-report">
              <div className="citizen-icon"><Camera size={24} /></div>
              <div><span className="section-eyebrow">COMMUNITY OBSERVATION</span><h2>Report Possible Landslide</h2><p>Geo-tagged photo/video reporting for community observations and administrator verification.</p><button className="button-primary" type="button" onClick={() => setReportOpen(true)}>Open report form <ChevronRight size={16} /></button></div>
            </section>
            <div className="readiness-note"><RadioTower size={18} /><div><strong>Low-bandwidth mode</strong><span>Ready for operational implementation</span></div></div>
          </div>
        </div>
      </main>
      <footer><strong>SIH26001 · Sikkim Pilot</strong><p>Decision-support early warning system powered by validated ML models (Roy et al. 2025 &amp; NASA LHASA 2.0).</p><span style={{ background: '#138b9c', color: '#fff' }}>LIVE ML SYSTEM ACTIVE</span></footer>
      <CitizenReportModal open={reportOpen} onClose={closeReport} />
    </div>
  )
}
