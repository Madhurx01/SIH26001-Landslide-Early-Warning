import { useCallback, useEffect, useState } from 'react'
import { Camera, ChevronRight, Gauge, RadioTower, ShieldAlert, KeyRound } from 'lucide-react'
import Header from './components/Header'
import TimelineController from './components/TimelineController'
import SummaryCards from './components/SummaryCards'
import RiskMap from './components/RiskMap'
import SelectedCellPanel from './components/SelectedCellPanel'
import WeatherRiskPanel from './components/WeatherRiskPanel'
import RoadRiskPanel from './components/RoadRiskPanel'
import HighwayInspectorModal from './components/HighwayInspectorModal'
import EmergencyPriorityPanel from './components/EmergencyPriorityPanel'
import AlertsPanel from './components/AlertsPanel'
import CitizenReportModal from './components/CitizenReportModal'
import AuthModal from './components/AuthModal'
import ReportVerificationPanel from './components/ReportVerificationPanel'
import api from './services/api'
import authService, { PRESET_USERS } from './services/auth'
import reportService from './services/reports'

const labels = {
  en: { title: 'AI-Based Landslide Early Warning & Risk Monitoring', pilot: 'Pilot', systemStatus: 'System Status', language: 'Language', dashboard: 'Dashboard', riskMap: 'Risk Map', citizenReport: 'Citizen Report' },
  hi: { title: 'AI आधारित भूस्खलन पूर्व चेतावनी एवं जोखिम निगरानी', pilot: 'पायलट', systemStatus: 'सिस्टम स्थिति', language: 'भाषा', dashboard: 'डैशबोर्ड', riskMap: 'जोखिम मानचित्र', citizenReport: 'नागरिक रिपोर्ट' },
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => authService.getCurrentUser() || PRESET_USERS.admin)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [citizenReports, setCitizenReports] = useState(() => reportService.getInitialReports())
  const [data, setData] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [telemetryMode, setTelemetryMode] = useState('live') // 'live' or 'storm'
  const [selectedDate, setSelectedDate] = useState('2021-10-19')
  const [inspectedRoad, setInspectedRoad] = useState(null)
  const [language, setLanguage] = useState('en')
  const [reportOpen, setReportOpen] = useState(false)
  const [acknowledged, setAcknowledged] = useState([])

  useEffect(() => {
    const fetchData = () => {
      api.getDashboard().then((dashboard) => {
        setData(dashboard)
        if (!selectedCell && dashboard.riskCells && dashboard.riskCells.length > 0) {
          setSelectedCell(dashboard.riskCells[0])
        }
      })
    }

    const fetchPooledReports = () => {
      reportService.getReports().then((reps) => {
        if (reps && reps.length > 0) {
          setCitizenReports(reps)
        }
      })
    }

    fetchData()
    fetchPooledReports()

    // Auto-poll live cloud radar feeds every 60 seconds
    const pollInterval = setInterval(fetchData, 60000)
    // Auto-poll shared pooled citizen reports every 3 seconds for real-time mobile sync
    const reportPollInterval = setInterval(fetchPooledReports, 3000)

    return () => {
      clearInterval(pollInterval)
      clearInterval(reportPollInterval)
    }
  }, [selectedCell])

  const closeReport = useCallback(() => setReportOpen(false), [])

  const handleSelectDate = (date) => {
    setSelectedDate(date)
    setTelemetryMode('timeline')
    if (data && data.timelineSnapshots && data.timelineSnapshots[date]) {
      const snap = data.timelineSnapshots[date]
      if (selectedCell) {
        const found = snap.riskCells.find((c) => c.cell_id === selectedCell.cell_id)
        if (found) setSelectedCell(found)
      }
    }
  }

  const switchMode = (mode) => {
    setTelemetryMode(mode)
    if (mode === 'live') {
      if (data && data.riskCells) {
        if (selectedCell) {
          const found = data.riskCells.find((c) => c.cell_id === selectedCell.cell_id)
          if (found) setSelectedCell(found)
        }
      }
    } else if (mode === 'storm') {
      handleSelectDate('2021-10-19')
    }
  }

  const viewAlertOnMap = (cellId) => {
    const activeCells = currentRiskCells
    const cell = activeCells.find((item) => item.cell_id === cellId)
    if (cell) setSelectedCell(cell)
    document.getElementById('risk-map')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const focusRoadOnMap = (road) => {
    document.getElementById('risk-map')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (!data) {
    return <main className="loading-screen"><div className="loading-mark"><Gauge size={26} /></div><strong>Preparing risk monitoring console</strong><span>Loading live ML early warning feeds…</span></main>
  }

  // Active snapshot calculation based on mode & timeline selection
  const currentSnapshot = (data.timelineSnapshots && data.timelineSnapshots[selectedDate]) || null
  const currentRiskCells = (telemetryMode === 'live') ? data.riskCells : (currentSnapshot ? currentSnapshot.riskCells : data.riskCells)
  const currentMetaSummary = (telemetryMode === 'live') ? data.meta.summary : (currentSnapshot ? {
    severe_risk_cells: currentSnapshot.meta.severe_count,
    high_risk_cells: currentSnapshot.meta.high_count,
    roads_at_risk: currentSnapshot.meta.severe_count > 500 ? 5 : currentSnapshot.meta.severe_count > 100 ? 3 : 0,
    settlements_at_risk: currentSnapshot.meta.severe_count > 500 ? 7 : 2,
    weather_trigger: `NASA IMERG Rain (${currentSnapshot.meta.weather_summary.rainfall_3d} mm 3d) & SMAP Saturation (${currentSnapshot.meta.weather_summary.soil_moisture}%)`
  } : data.meta.summary)

  return (
    <div className="app">
      <Header
        meta={data.meta}
        language={language}
        onLanguageChange={setLanguage}
        labels={labels[language]}
        currentUser={currentUser}
        onOpenAuth={() => setAuthModalOpen(true)}
      />
      <main className="main-content" id="dashboard">
        {/* Interactive Mode Toggle Bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          background: '#0a3d46',
          border: '1px solid #19717e',
          borderRadius: '10px',
          padding: '0.75rem 1.1rem',
          marginBottom: '1rem',
          color: '#fff'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <RadioTower size={18} style={{ color: '#26d0ce' }} />
            <div>
              <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600 }}>
                <strong>Operational Early Warning Mode:</strong> Dual-Layer ML System Active (Static Susceptibility &amp; Dynamic Meteorological Trigger).
              </p>
              <span style={{ fontSize: '0.72rem', color: '#9ec8b9' }}>
                Mode: {telemetryMode === 'live' ? '🛰️ Real-Time Live Satellite Telemetry Active (Open-Meteo Feed)' : '🚨 Extreme Disaster Storm Simulation (19 Oct)'}
              </span>
            </div>
          </div>

          {/* Interactive Toggle Switch */}
          <div style={{
            display: 'flex',
            background: 'rgba(0, 0, 0, 0.3)',
            padding: '3px',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.15)'
          }}>
            <button
              type="button"
              onClick={() => switchMode('live')}
              style={{
                background: telemetryMode === 'live' ? '#097969' : 'transparent',
                color: '#fff',
                border: 'none',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.2s ease',
                boxShadow: telemetryMode === 'live' ? '0 2px 8px rgba(0,0,0,0.3)' : 'none'
              }}
            >
              🛰️ Live Satellite Radar (Today)
            </button>
            <button
              type="button"
              onClick={() => switchMode('storm')}
              style={{
                background: telemetryMode !== 'live' ? '#d7191c' : 'transparent',
                color: '#fff',
                border: 'none',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.2s ease',
                boxShadow: telemetryMode !== 'live' ? '0 2px 8px rgba(215, 25, 28, 0.4)' : 'none'
              }}
            >
              🚨 Simulate Disaster Storm (19 Oct)
            </button>
          </div>
        </div>

        {/* Feature 1: The Time Machine Monsoon Slider */}
        <TimelineController
          milestones={data.milestones}
          selectedDate={selectedDate}
          onSelectDate={handleSelectDate}
          meta={currentSnapshot ? currentSnapshot.meta : null}
        />

        <SummaryCards summary={currentMetaSummary} />

        <div className="primary-grid">
          <RiskMap
            riskCells={currentRiskCells}
            roads={data.roads}
            settlements={data.settlements}
            historicalLandslides={data.historicalLandslides}
            boundaryGeoJson={data.sikkimBoundary}
            selectedCell={selectedCell}
            onSelectCell={setSelectedCell}
          />
          {/* Feature 2: Visual SHAP Diverging Factor Bars in Selected Cell Panel */}
          <SelectedCellPanel cell={selectedCell} />
        </div>

        <div className="analysis-grid">
          <WeatherRiskPanel weather={data.weather} />
          <AlertsPanel
            alerts={data.alerts}
            acknowledged={acknowledged}
            onAcknowledge={(id) => setAcknowledged((current) => [...current, id])}
            onView={viewAlertOnMap}
            isAdmin={currentUser?.role === 'admin'}
          />
        </div>

        {/* Feature 3: Highway Lifeline Inspector */}
        <RoadRiskPanel
          roads={data.roads}
          onInspectRoad={(road) => setInspectedRoad(road)}
        />

        {/* RBAC Admin Incident Verification Queue */}
        {currentUser?.role === 'admin' && (
          <div id="verification-queue" style={{ marginBottom: '1.5rem' }}>
            <ReportVerificationPanel
              reports={citizenReports}
              onStatusChange={(updated) => setCitizenReports(updated)}
            />
          </div>
        )}

        <div className="operations-grid">
          {currentUser?.role !== 'viewer' ? (
            <EmergencyPriorityPanel priorities={data.emergencyPriorities} />
          ) : (
            <section className="panel" style={{ borderLeft: '4px solid #27865f' }}>
              <div className="panel-header">
                <h2>Citizen Safety &amp; Evacuation Advisory</h2>
                <span className="badge" style={{ background: '#27865f', color: '#fff' }}>Public Portal</span>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#cad5e2', lineHeight: 1.5 }}>
                Stay alert along river valleys (Teesta Basin) and steep road cuttings. If traveling on NH-10 or towards North Sikkim (Lachen/Lachung), verify live road clearance status above before departure.
              </p>
              <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.06)', padding: '4px 10px', borderRadius: '6px' }}>
                  📞 State Emergency Helpline: <strong>1070</strong> / <strong>112</strong>
                </span>
                <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.06)', padding: '4px 10px', borderRadius: '6px' }}>
                  🚧 BRO Control Room: <strong>03592-202288</strong>
                </span>
              </div>
            </section>
          )}

          <div className="support-column">
            <section className="panel citizen-card" id="citizen-report">
              <div className="citizen-icon"><Camera size={24} /></div>
              <div>
                <span className="section-eyebrow">COMMUNITY OBSERVATION</span>
                <h2>Report Possible Landslide</h2>
                <p>Geo-tagged photo/video reporting for community observations and administrator verification.</p>
                <button className="button-primary" type="button" onClick={() => setReportOpen(true)}>
                  Open report form <ChevronRight size={16} />
                </button>
              </div>
            </section>
            <div className="readiness-note">
              <RadioTower size={18} />
              <div>
                <strong>Low-bandwidth mode</strong>
                <span>Edge server caching enabled for Himalayan terrain</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer>
        <strong>SIH26001 · AAPTIRAKSHAK · Sikkim Pilot</strong>
        <p>Decision-support early warning system powered by Dual-Layer Machine Learning (Static Susceptibility &amp; Dynamic Meteorological Radar).</p>
        <span style={{ background: '#138b9c', color: '#fff' }}>
          SESSION: {currentUser?.role?.toUpperCase()} ({currentUser?.name})
        </span>
      </footer>

      <CitizenReportModal
        open={reportOpen}
        onClose={closeReport}
        onReportSubmitted={(newR) => setCitizenReports(reportService.getReports())}
      />
      
      {/* Highway Lifeline Inspector Modal */}
      {inspectedRoad && (
        <HighwayInspectorModal
          road={inspectedRoad}
          onClose={() => setInspectedRoad(null)}
          onFocusMap={focusRoadOnMap}
        />
      )}

      {/* RBAC & JWT Authentication Modal */}
      <AuthModal
        open={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        currentUser={currentUser}
        onLogin={(roleKey) => setCurrentUser(authService.login(roleKey))}
      />
    </div>
  )
}
