import { ArrowRight, ShieldAlert } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function EmergencyPriorityPanel({ priorities, exposureMeta }) {
  const displayed = priorities.slice(0, 50)
  return (
    <section className="panel priority-panel">
      <div className="panel-heading"><div><span className="section-eyebrow"><ShieldAlert size={14} /> GIS ACTION QUEUE</span><h2>Emergency Review Priority</h2><p>P1 {exposureMeta?.priority_counts?.P1 ?? 0} · P2 {exposureMeta?.priority_counts?.P2 ?? 0} · P3 {exposureMeta?.priority_counts?.P3 ?? 0}</p></div></div>
      <div className="priority-list">
        {displayed.map((item) => (
          <article className="priority-item" key={item.priority_id}>
            <div className="priority-rank"><span>RANK {item.rank}</span><strong>{item.priority_class}</strong></div>
            <div className="priority-content">
              <div className="priority-title"><SeverityBadge level={item.risk_level} subtle /><strong>{item.location}</strong><small>{item.cell_id}</small></div>
              <div className="priority-exposure">Potential exposure: <strong>{item.exposure}</strong></div>
              <div className="priority-exposure">Index: <strong>{item.operational_risk_index}</strong> · Forecast 24/48/72h: <strong>{item.forecast_operational_risk_index_24h} / {item.forecast_operational_risk_index_48h} / {item.forecast_operational_risk_index_72h}</strong></div>
              <p>{item.reason}</p>
              <div className="recommended-action"><ArrowRight size={15} /><span><small>RECOMMENDED ACTION</small>{item.recommended_action}</span></div>
            </div>
          </article>
        ))}
      </div>
      <p className="panel-note">Showing the first {displayed.length} of {priorities.length} ranked cells. P1: SEVERE with mapped exposure or verified incident in a HIGH/SEVERE cell. P2: HIGH with mapped exposure. P3: SEVERE without mapped exposure. Recommendations require human review and are not blockage declarations, evacuation orders, or automatic dispatches.</p>
    </section>
  )
}
