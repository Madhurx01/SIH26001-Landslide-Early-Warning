import { Activity, ChevronDown, Languages, MapPinned, RadioTower, ShieldCheck, UserCheck, Eye, KeyRound } from 'lucide-react'

export default function Header({ meta, language, onLanguageChange, labels, currentUser, onOpenAuth }) {
  const getRoleIcon = (role) => {
    if (role === 'admin') return <ShieldCheck size={15} style={{ color: '#ff8a93' }} />
    if (role === 'analyst') return <UserCheck size={15} style={{ color: '#4dd4e8' }} />
    return <Eye size={15} style={{ color: '#74e0b1' }} />
  }

  const getRoleColor = (role) => {
    if (role === 'admin') return '#c7353f'
    if (role === 'analyst') return '#138b9c'
    return '#27865f'
  }

  return (
    <>
      <div className="gov-strip">
        <span>भारत सरकार · Government of India · National Disaster Management System</span>
        <span className="gov-strip__right"><RadioTower size={13} /> Secure Early Warning &amp; Response Console</span>
      </div>
      <header className="app-header">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true"><MapPinned size={25} /></div>
          <div>
            <div className="brand-kicker">SIH26001 · AAPTIRAKSHAK</div>
            <h1>{labels.title}</h1>
            <p>{labels.pilot}: {meta.pilot_region}</p>
          </div>
        </div>
        <div className="header-controls">
          {/* RBAC User Profile / Switcher */}
          {currentUser && (
            <button
              type="button"
              onClick={onOpenAuth}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'rgba(255, 255, 255, 0.06)',
                border: `1.5px solid ${getRoleColor(currentUser.role)}`,
                borderRadius: '8px',
                padding: '6px 12px',
                color: '#fff',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s ease'
              }}
              title="Click to switch Role / JWT Session"
            >
              {getRoleIcon(currentUser.role)}
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, lineHeight: 1.1 }}>
                  {currentUser.role === 'viewer' ? 'Tenzing Lepcha (Citizen)' : currentUser.role === 'analyst' ? 'Dr. P. Roy (GIS Lead)' : currentUser.name}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#cad5e2', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {currentUser.role === 'viewer' ? 'PUBLIC CITIZEN' : currentUser.role === 'analyst' ? 'GIS SCIENTIST (ANALYST)' : 'DISASTER COMMANDER (ADMIN)'}
                </div>
              </div>
              <KeyRound size={13} style={{ color: '#9ec8b9', marginLeft: '4px' }} />
            </button>
          )}

          <div className="monitoring-status"><Activity size={16} /><span>{labels.systemStatus}</span><strong>{meta.system_status}</strong></div>
          <label className="language-control">
            <Languages size={16} />
            <span>{labels.language}</span>
            <select value={language} onChange={(event) => onLanguageChange(event.target.value)} aria-label="Language">
              <option value="en">English</option>
              <option value="ne">नेपाली (Nepali)</option>
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
        {currentUser?.role === 'admin' && (
          <a href="#verification-queue" style={{ color: '#ff8a93', fontWeight: 700 }}>
            🛡️ Report Verification Queue
          </a>
        )}
        <a href="#system-status">{labels.systemStatus}</a>
        <div className="nav-spacer" />
        <span className="updated-label">Last updated <strong>{meta.last_updated}</strong></span>
        <span className="demo-badge" style={{ background: getRoleColor(currentUser?.role || 'admin') }}>
          {currentUser?.role?.toUpperCase() || 'SECURE'} SESSION
        </span>
      </nav>
    </>
  )
}
