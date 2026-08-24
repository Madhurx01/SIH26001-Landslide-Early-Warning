import { ArrowRight, ShieldAlert } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function EmergencyPriorityPanel({ priorities, limit }) {
  const visiblePriorities = typeof limit === 'number' ? priorities.slice(0, limit) : priorities

  return (
    <section className="panel priority-panel">
      <div className="panel-heading"><div><span className="section-eyebrow"><ShieldAlert size={14} /> ACTION QUEUE</span><h2>Operational Priorities</h2><p>Real road/settlement exposure · 19 Oct 2021 replay</p></div><span className="workflow-label">REAL EXPOSURE</span></div>
      <div className="priority-list">
        {visiblePriorities.map((item) => (
          <article className="priority-item" key={`${item.cell_id}-${item.location}`}>
            <div className="priority-rank"><span>PRIORITY</span><strong>{item.priority}</strong></div>
            <div className="priority-content">
              <div className="priority-title"><SeverityBadge level={item.risk_level} subtle /><strong>{item.location}</strong></div>
              <div className="priority-exposure">{item.cell_id} · Operational Risk Index: <strong>{Number(item.final_risk_score).toFixed(1)} / 100</strong></div>
              <p>Potential exposure: {item.exposure}</p>
              <div className="recommended-action"><ArrowRight size={15} /><span><small>RECOMMENDED ACTION</small>{item.recommended_action}</span></div>
            </div>
          </article>
        ))}
      </div>
      <p className="panel-note">Field verification recommended. Priorities are decision support, not automatic government orders.</p>
    </section>
  )
}
