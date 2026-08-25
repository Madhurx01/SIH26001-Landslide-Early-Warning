import { BellRing, Check, Eye, Radio } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function AlertsPanel({ alerts, acknowledged, onAcknowledge, onView, isAdmin }) {
  return (
    <section className="panel alerts-panel">
      <div className="panel-heading"><div><span className="section-eyebrow"><BellRing size={14} /> WARNING DESK</span><h2>Active Warnings</h2></div><span className="alert-count">{alerts.length - acknowledged.length} ACTIVE</span></div>
      <div className="alerts-list">
        {alerts.map((alert) => {
          const isAcknowledged = acknowledged.includes(alert.alert_id)
          return (
            <article className={isAcknowledged ? 'alert-item is-acknowledged' : 'alert-item'} key={alert.alert_id}>
              <div className="alert-severity"><SeverityBadge level={alert.risk_level} /><small>{alert.alert_id}</small></div>
              <div className="alert-content"><strong>{alert.title}</strong><p>{alert.detail}</p><div className="channels"><Radio size={13} />Broadcast channels: {alert.channels.map((channel) => <span key={channel}>{channel}</span>)}</div></div>
              <div className="alert-actions">
                {isAdmin ? (
                  <button type="button" className="button-secondary" onClick={() => onAcknowledge(alert.alert_id)} disabled={isAcknowledged}>
                    {isAcknowledged ? <><Check size={15} /> Acknowledged</> : 'Acknowledge Alert'}
                  </button>
                ) : (
                  <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontStyle: 'italic', padding: '4px 8px' }}>
                    Citizen Public Broadcast
                  </span>
                )}
                <button type="button" className="button-primary" onClick={() => onView(alert.location_cell_id)}><Eye size={15} /> View on map</button>
              </div>
            </article>
          )
        })}
      </div>
      <p className="panel-note">Official state disaster broadcast feeds powered by NDMA 4-color early warning framework.</p>
    </section>
  )
}
