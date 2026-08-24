import { BellRing, Languages, RadioTower, Route, Wifi } from 'lucide-react'
import DataSourceStatus from '../components/DataSourceStatus'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function SystemStatusPage({ data, language, onLanguageChange }) {
  return (
    <section className="route-page system-status-page" aria-label="System Status">
      <WorkspaceHeading eyebrow="DATA / MODEL / INTEGRATION TRANSPARENCY" title="System Status" description="Technical readiness and validation context for the SIH26001 historical replay prototype." badge="HISTORICAL REPLAY" />
      <DataSourceStatus sources={data.dataSources} modelInfo={data.modelInfo} />
      <div className="system-detail-grid">
        <section className="panel replay-detail-panel">
          <div className="panel-heading"><div><span className="section-eyebrow"><RadioTower size={14} /> REPLAY CONTEXT</span><h2>Model & Replay Window</h2></div></div>
          <dl className="status-definition-grid">
            <div><dt>Risk Engine</dt><dd>Static susceptibility + dynamic trigger</dd></div>
            <div><dt>Replay window</dt><dd>11 May 2021 – 19 Oct 2021</dd></div>
            <div><dt>Current demo</dt><dd>{data.meta.demo_date_display}</dd></div>
            <div><dt>Risk features</dt><dd>{data.meta.feature_count.toLocaleString('en-IN')} real model cells</dd></div>
          </dl>
          <p className="prototype-statement">This is a historical replay and decision-support prototype, not a live operational government warning service.</p>
        </section>
        <section className="panel readiness-panel">
          <div className="panel-heading"><div><span className="section-eyebrow">INTEGRATION READINESS</span><h2>Operational Modules</h2></div></div>
          <div className="readiness-status-list">
            <div><Route size={18} /><span><strong>Road exposure</strong>Real refined OSM vehicular-road intersections integrated</span></div>
            <div><Route size={18} /><span><strong>Settlement exposure</strong>Real named OSM settlement intersections integrated</span></div>
            <div><BellRing size={18} /><span><strong>Notifications</strong>Prototype readiness · no external alert sent</span></div>
            <label><Languages size={18} /><span><strong>Multilingual</strong><select value={language} onChange={(event) => onLanguageChange(event.target.value)} aria-label="Language"><option value="en">English</option><option value="hi">हिन्दी</option></select></span></label>
            <div><Wifi size={18} /><span><strong>Offline / low bandwidth</strong>Future implementation ready</span></div>
          </div>
        </section>
      </div>
    </section>
  )
}
