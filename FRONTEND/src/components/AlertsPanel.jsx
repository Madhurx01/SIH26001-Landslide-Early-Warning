import { BellRing, Check, Eye, Radio } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

export default function AlertsPanel({ alerts, acknowledged, onAcknowledge, onView }) {
  return (
    <section className="panel alerts-panel">
      <div className="panel-heading"><div><span className="section-eyebrow"><BellRing size={14} /> WARNING DESK</span><h2>Active Warnings</h2></div><span className="alert-count">{alerts.length - acknowledged.length} ACTIVE</span></div>
      <div className="alerts-list">
        {alerts.map((alert) => {
          const isAcknowledged = acknowledged.includes(alert.alert_id)
          return (
            <article className={isAcknowledged ? 'alert-item is-acknowledged' : 'alert-item'} key={alert.alert_id}>
              <div className="alert-severity"><SeverityBadge level={alert.risk_level} /><small>{alert.alert_id}</small></div>
              <div className="alert-content"><strong>{alert.title}</strong><p>{alert.detail}</p><div className="channels"><Radio size={13} />Future channels: {alert.channels.map((channel) => <span key={channel}>{channel}</span>)}</div></div>
              <div className="alert-actions">
                <button type="button" className="button-secondary" onClick={() => onAcknowledge(alert.alert_id)} disabled={isAcknowledged}>{isAcknowledged ? <><Check size={15} /> Acknowledged</> : 'Acknowledge'}</button>
                <button type="button" className="button-primary" onClick={() => onView(alert.location_cell_id)}><Eye size={15} /> View on map</button>
              </div>
            </article>
          )
        })}
      </div>
      <p className="panel-note">Delivery channels are interface placeholders; no SMS or community alert has been sent.</p>
    </section>
  )
}
