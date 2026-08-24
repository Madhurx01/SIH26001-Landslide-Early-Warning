import RiskMap from '../components/RiskMap'
import SelectedCellPanel from '../components/SelectedCellPanel'
import WorkspaceHeading from '../components/WorkspaceHeading'

export default function RiskMapPage({ mapProps, selectedCell }) {
  return (
    <section className="route-page risk-map-page" aria-label="Risk Map">
      <WorkspaceHeading eyebrow="DETAILED GIS ANALYSIS" title="Risk Map" description="Interactive analysis of 7,390 real model risk features for the 19 Oct 2021 historical replay." badge="REAL MODEL REPLAY" />
      <div className="primary-grid risk-analysis-grid">
        <RiskMap {...mapProps} />
        <SelectedCellPanel cell={selectedCell} />
      </div>
    </section>
  )
}
