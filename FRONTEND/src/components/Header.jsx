import { Activity, ChevronDown, Languages, MapPinned, RadioTower } from 'lucide-react'

export default function Header({ meta, language, onLanguageChange, labels }) {
  return (
    <>
      <div className="gov-strip">
        <span>भारत सरकार · Government of India</span>
        <span className="gov-strip__right"><RadioTower size={13} /> Prototype decision-support console</span>
      </div>
      <header className="app-header">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true"><MapPinned size={25} /></div>
          <div>
            <div className="brand-kicker">SIH26001</div>
            <h1>{labels.title}</h1>
            <p>{labels.pilot}: {meta.pilot_region}</p>
          </div>
        </div>
        <div className="header-controls">
          <div className="monitoring-status"><Activity size={16} /><span>{labels.systemStatus}</span><strong>{meta.system_status}</strong></div>
          <label className="language-control">
            <Languages size={16} />
            <span>{labels.language}</span>
            <select value={language} onChange={(event) => onLanguageChange(event.target.value)} aria-label="Language">
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </label>
        </div>
      </header>
      <nav className="main-nav" aria-label="Primary navigation">
        <a href="#dashboard" className="active">{labels.dashboard}</a>
        <a href="#risk-map">{labels.riskMap}</a>
        <a href="#citizen-report">{labels.citizenReport}</a>
        <a href="#system-status">{labels.systemStatus}</a>
        <div className="nav-spacer" />
        <span className="updated-label">Last updated <strong>{meta.last_updated}</strong></span>
        <span className="demo-badge">{meta.data_mode}</span>
      </nav>
    </>
  )
}
