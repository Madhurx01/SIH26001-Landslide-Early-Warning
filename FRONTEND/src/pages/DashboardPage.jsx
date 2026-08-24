import SummaryCards from '../components/SummaryCards'
import RiskMap from '../components/RiskMap'
import SelectedCellPanel from '../components/SelectedCellPanel'
import WeatherRiskPanel from '../components/WeatherRiskPanel'
import AlertsPanel from '../components/AlertsPanel'
import EmergencyPriorityPanel from '../components/EmergencyPriorityPanel'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function DashboardPage({ data, mapProps, selectedCell, acknowledged, onAcknowledge, onViewAlert, onViewAllWarnings }) {
  return (
    <section className="route-page dashboard-page" aria-label="Dashboard">
      <WorkspaceHeading eyebrow="EXECUTIVE / OPERATIONS OVERVIEW" title="Dashboard" description="Concise decision-support overview for the 19 Oct 2021 Sikkim historical replay." />
      <SummaryCards summary={data.meta.summary} />
      <div className="primary-grid dashboard-primary-grid">
        <RiskMap {...mapProps} />
        <SelectedCellPanel cell={selectedCell} compact />
      </div>
      <div className="dashboard-support-grid">
        <WeatherRiskPanel weather={data.weather} />
        <AlertsPanel alerts={data.alerts} acknowledged={acknowledged} onAcknowledge={onAcknowledge} onView={onViewAlert} limit={2} onViewAll={onViewAllWarnings} />
        <EmergencyPriorityPanel priorities={data.emergencyPriorities} limit={2} />
      </div>
    </section>
  )
}
