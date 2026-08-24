import { Camera, ChevronRight, Clock3, MapPin, ShieldCheck } from 'lucide-react'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function CitizenReportsPage({ onOpenReport }) {
  return (
    <section className="route-page citizen-reports-page" aria-label="Citizen Reports">
      <WorkspaceHeading eyebrow="COMMUNITY OBSERVATIONS" title="Citizen Reports" description="Prototype geotagged landslide reporting for administrator and field verification." badge="FRONTEND PROTOTYPE" />
      <div className="citizen-workspace-grid">
        <section className="panel citizen-card citizen-page-card">
          <div className="citizen-icon"><Camera size={22} /></div>
          <div>
            <span className="section-eyebrow">COMMUNITY OBSERVATION</span>
            <h2>Report Possible Landslide</h2>
            <p>Share a location, description, observed time, and photo or video where safely available. Do not enter hazardous areas to collect evidence.</p>
            <button className="button-primary" type="button" onClick={onOpenReport}>Open report form <ChevronRight size={16} /></button>
          </div>
        </section>
        <section className="panel verification-panel">
          <div className="panel-heading"><div><span className="section-eyebrow"><ShieldCheck size={14} /> VERIFICATION REQUIRED</span><h2>Report handling</h2><p>No server or report database is connected in this prototype.</p></div></div>
          <div className="verification-steps">
            <div><MapPin size={18} /><span><strong>Geotag review</strong>Confirm the submitted location.</span></div>
            <div><Camera size={18} /><span><strong>Evidence review</strong>Check media and description.</span></div>
            <div><Clock3 size={18} /><span><strong>Field verification</strong>Administrator or field confirmation required.</span></div>
          </div>
        </section>
      </div>
      <p className="route-disclaimer">Citizen observations are unverified until reviewed by an administrator or field team. Prototype submissions are not transmitted or stored.</p>
    </section>
  )
}
