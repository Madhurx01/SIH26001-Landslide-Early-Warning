import { BellRing, Check, Eye } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function AlertsPanel({ alerts, acknowledged, onAcknowledge, onView, limit, onViewAll }) {
  const visibleAlerts = typeof limit === 'number' ? alerts.slice(0, limit) : alerts

  return (
    <section className="panel alerts-panel" id="active-warnings">
      <div className="panel-heading"><div><span className="section-eyebrow"><BellRing size={14} /> VERIFICATION DESK</span><h2>Replay Priority Notices</h2></div><div className="panel-heading-tags"><span className="workflow-label">REAL REPLAY PRIORITIES</span><span className="alert-count">{alerts.length - acknowledged.length} ACTIVE</span></div></div>
      <div className="alerts-list">
        {visibleAlerts.map((alert) => {
          const isAcknowledged = acknowledged.includes(alert.alert_id)
          return (
            <article className={isAcknowledged ? 'alert-item is-acknowledged' : 'alert-item'} key={alert.alert_id}>
              <div className="alert-severity"><SeverityBadge level={alert.risk_level} /><small>{alert.alert_id}</small></div>
              <div className="alert-content">
                <strong>{alert.title}</strong>
                <div className="alert-meta"><span>{alert.location_cell_id}</span><span>19 Oct 2021 · historical replay</span></div>
                <p>{alert.detail}</p>
              </div>
              <div className="alert-actions">
                <button type="button" className="button-secondary" onClick={() => onAcknowledge(alert.alert_id)} disabled={isAcknowledged}>{isAcknowledged ? <><Check size={15} /> Acknowledged</> : 'Acknowledge'}</button>
                <button type="button" className="button-primary" onClick={() => onView(alert.location_cell_id)}><Eye size={15} /> View on map</button>
              </div>
            </article>
          )
        })}
      </div>
      {onViewAll && <div className="panel-link-row"><button className="button-secondary" type="button" onClick={onViewAll}>View all priorities</button></div>}
      <p className="panel-note">Potential exposure only. No external alert has been sent; field verification is recommended.</p>
    </section>
  )
}
