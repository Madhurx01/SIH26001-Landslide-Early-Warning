import { Activity, Clock3 } from 'lucide-react'

export default function Header({ meta, labels }) {
  return (
    <header className="app-header">
      <div className="brand-block">
        <div>
          <h1>{labels.title}</h1>
          <p>Sikkim {labels.pilot}</p>
        </div>
      </div>
      <div className="header-controls">
        <div className="monitoring-status"><Activity size={16} /><span>{labels.systemStatus}</span><strong>{meta.system_status}</strong></div>
        <span className="header-demo-badge">{meta.data_mode}</span>
        <div className="header-updated"><Clock3 size={15} /><span>Replay date<strong>{meta.last_updated}</strong></span></div>
      </div>
    </header>
  )
}