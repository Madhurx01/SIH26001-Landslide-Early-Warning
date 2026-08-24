import { severityConfig } from '../data/mockRiskData'

export default function RiskLegend() {
  return (
    <div className="map-legend" aria-label="Risk severity legend">
      <strong>RISK SEVERITY</strong>
      {Object.entries(severityConfig).map(([level, config]) => (
        <div key={level}><span style={{ backgroundColor: config.color }} />{level}</div>
      ))}
      <small>Operational ML Prediction</small>
    </div>
  )
}
