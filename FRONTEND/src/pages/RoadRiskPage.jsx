import { Route } from 'lucide-react'
import RoadRiskPanel from '../components/RoadRiskPanel'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function RoadRiskPage({ roads, exposureSummary }) {
  return (
    <section className="route-page road-risk-page" aria-label="Road Risk">
      <WorkspaceHeading eyebrow="TRANSPORT CONNECTIVITY / EXPOSURE" title="Road Risk" description="Real refined OSM vehicular-road exposure for the 19 Oct 2021 historical replay." badge="REAL OSM EXPOSURE" />
      <RoadRiskPanel roads={roads} summary={exposureSummary} />
      <section className="panel integration-explainer">
        <Route size={22} />
        <div>
          <span className="section-eyebrow">EXPOSURE METHOD</span>
          <h3>Real HIGH/SEVERE risk cells + refined OSM vehicular roads</h3>
          <p>Potential exposure is a spatial intersection for prioritizing field verification. It does not confirm road damage, blockage, or closure.</p>
        </div>
      </section>
    </section>
  )
}
