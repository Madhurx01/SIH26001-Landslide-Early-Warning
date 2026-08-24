import AlertsPanel from '../components/AlertsPanel'
import EmergencyPriorityPanel from '../components/EmergencyPriorityPanel'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function WarningsPage({ alerts, priorities, priorityCounts, acknowledged, onAcknowledge, onView }) {
  return (
    <section className="route-page warnings-page" aria-label="Operational Priorities and Warnings">
      <WorkspaceHeading eyebrow="WARNING MANAGEMENT / FIELD VERIFICATION" title="Operational Priorities" description="Real P1/P2/P3 priorities from the 19 Oct 2021 risk replay and OSM exposure analysis." badge="REAL REPLAY EXPOSURE" />
      <div className="module-kpis" aria-label="Operational priority summary">
        <article><span>Priority 1</span><strong>{priorityCounts[1]}</strong></article>
        <article><span>Priority 2</span><strong>{priorityCounts[2]}</strong></article>
        <article><span>Priority 3</span><strong>{priorityCounts[3]}</strong></article>
        <article><span>Context</span><strong className="is-text">19 Oct 2021 replay</strong></article>
      </div>
      <EmergencyPriorityPanel priorities={priorities} />
      <AlertsPanel alerts={alerts} acknowledged={acknowledged} onAcknowledge={onAcknowledge} onView={onView} />
      <p className="route-disclaimer">Potential exposure does not confirm damage or closure. No external alert has been sent; field verification remains required.</p>
    </section>
  )
}
