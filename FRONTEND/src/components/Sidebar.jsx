import { BellRing, Camera, Database, LayoutDashboard, Map, MapPinned, Route } from 'lucide-react'

const navItems = [
  { route: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { route: '/risk-map', label: 'Risk Map', icon: Map },
  { route: '/warnings', label: 'Active Warnings', icon: BellRing },
  { route: '/road-risk', label: 'Road Risk', icon: Route },
  { route: '/citizen-reports', label: 'Citizen Reports', icon: Camera },
  { route: '/system-status', label: 'System Status', icon: Database },
]

export default function Sidebar({ currentRoute }) {
  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand__icon"><MapPinned size={22} /></div>
        <div><strong>SIH26001</strong><span>Landslide Early Warning</span><small>Sikkim Pilot</small></div>
      </div>
      <nav className="sidebar-nav" aria-label="Monitoring navigation">
        <span className="sidebar-nav__label">MONITORING</span>
        {navItems.map(({ route, label, icon: Icon }) => (
          <a key={route} href={'#' + route} className={route === currentRoute ? 'active' : undefined} aria-current={route === currentRoute ? 'page' : undefined}>
            <Icon size={17} /><span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar-environment">
        <span><i /> Historical Replay</span>
        <p>19 Oct 2021 · validated pipeline output with demonstration response workflows.</p>
      </div>
    </aside>
  )
}
