import { CloudRain, Droplets, Info, MapPinned, Mountain, Route, Ruler } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

function Metric({ icon: Icon, label, value }) {
  return <div className="detail-metric"><Icon size={16} /><span>{label}<strong>{value}</strong></span></div>
}

export default function SelectedCellPanel({ cell }) {
  if (!cell) return null
  return (
    <section className="panel selected-panel">
      <div className="panel-heading selected-heading">
        <div>
          <span className="section-eyebrow"><MapPinned size={14} /> SELECTED RISK LOCATION</span>
          <h2>{cell.cell_id}</h2>
        </div>
        <SeverityBadge level={cell.risk_level} />
      </div>
      <div className="risk-score-block">
        <h3>Predicted risk</h3>
        <div className="risk-score"><strong>{cell.risk_probability}%</strong><span>Risk probability</span></div>
        <div className="probability-track"><span style={{ width: `${cell.risk_probability}%` }} /></div>
        <small>Predicted risk · frontend demo value</small>
      </div>
      <div className="detail-section">
        <h3>Terrain</h3>
        <div className="detail-metrics two-col">
          <Metric icon={Ruler} label="Slope" value={`${cell.slope_deg}°`} />
          <Metric icon={Mountain} label="Elevation" value={`${cell.elevation_m.toLocaleString()} m`} />
        </div>
      </div>
      <div className="detail-section">
        <h3>Trigger conditions</h3>
        <div className="detail-metrics two-col">
          <Metric icon={CloudRain} label="Rainfall 24h" value={`${cell.rainfall_1d_mm} mm`} />
          <Metric icon={CloudRain} label="Rainfall 3-day" value={`${cell.rainfall_3d_mm} mm`} />
          <Metric icon={CloudRain} label="Rainfall 7-day" value={`${cell.rainfall_7d_mm} mm`} />
          <Metric icon={Droplets} label="Soil moisture" value={`${cell.soil_moisture}%`} />
        </div>
      </div>
      <div className="detail-section exposure-section">
        <h3>Potential exposure</h3>
        <div><Route size={16} /><span>Nearest road<strong>{cell.nearest_road} · {cell.road_distance_m} m</strong></span></div>
        <div><MapPinned size={16} /><span>Nearby settlement<strong>{cell.nearest_settlement} · {cell.settlement_distance_m} m</strong></span></div>
      </div>
      <div className="explanation-box"><Info size={17} /><p><strong>Risk explanation</strong>{cell.explanation}</p></div>
      <p className="mock-caveat">AI risk assessment computed via Roy et al. (2025) Static Model &amp; NASA LHASA 2.0 Dynamic Engine with SHAP feature attribution.</p>
    </section>
  )
}
