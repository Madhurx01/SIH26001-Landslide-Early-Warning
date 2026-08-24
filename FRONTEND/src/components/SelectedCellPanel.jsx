import { Activity, CloudRain, Droplets, Info, MapPinned, Route, ShieldAlert } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

const formatScore = (value) => `${Number(value).toFixed(1)} / 100`
const formatRainfall = (value) => value == null ? 'Unavailable' : `${Number(value).toFixed(1)} mm`

function Metric({ icon: Icon, label, value }) {
  return <div className="detail-metric"><Icon size={16} /><span>{label}<strong>{value}</strong></span></div>
}

export default function SelectedCellPanel({ cell, compact = false }) {
  if (!cell) return null
  const soilMoisture = cell.soil_moisture_percent == null
    ? 'Unavailable / quality-filtered'
    : `${cell.soil_moisture_percent.toFixed(1)}%`
  const priority = cell.operational_priority ? `P${cell.operational_priority}` : 'Not assigned'

  return (
    <section className={compact ? 'panel selected-panel selected-panel--compact' : 'panel selected-panel'}>
      <div className="panel-heading selected-heading">
        <div><span className="section-eyebrow"><MapPinned size={14} /> SELECTED RISK LOCATION</span><h2>{cell.cell_id}</h2><p>Real replay · 19 Oct 2021</p></div>
      </div>
      <div className="risk-score-block">
        <h3>Operational risk</h3>
        <div className="risk-score">
          <div><strong>{formatScore(cell.final_risk_score)}</strong><span>Operational Risk Index</span></div>
          <div className="risk-level"><small>Risk level</small><SeverityBadge level={cell.risk_level} /></div>
        </div>
        <div className="probability-track"><span style={{ width: `${cell.final_risk_score}%` }} /></div>
        <small>MVP operational category · not a forecast certainty</small>
      </div>
      {!compact && (
        <>
          <div className="detail-section">
            <h3>Model signals</h3>
            <div className="detail-metrics two-col">
              <Metric icon={Activity} label="Static susceptibility" value={formatScore(cell.static_susceptibility)} />
              <Metric icon={Activity} label="Dynamic trigger" value={formatScore(cell.dynamic_trigger_score)} />
              <Metric icon={MapPinned} label="Cell coordinates" value={[cell.latitude.toFixed(4), cell.longitude.toFixed(4)].join(', ')} />
            </div>
          </div>
          <div className="detail-section">
            <h3>Trigger conditions</h3>
            <div className="detail-metrics two-col">
              <Metric icon={CloudRain} label="Rainfall 24h" value={formatRainfall(cell.rainfall_1d_mm)} />
              <Metric icon={CloudRain} label="Rainfall 3-day" value={formatRainfall(cell.rainfall_3d_mm)} />
              <Metric icon={CloudRain} label="Rainfall 7-day" value={formatRainfall(cell.rainfall_7d_mm)} />
              <Metric icon={Droplets} label="Soil moisture" value={soilMoisture} />
            </div>
          </div>
        </>
      )}
      <div className="detail-section exposure-section">
        <h3>Potential exposure</h3>
        <div><Route size={16} /><span>Road<strong>{cell.road_exposure_status}</strong></span></div>
        <div><MapPinned size={16} /><span>Settlement<strong>{cell.settlement_exposure_status}</strong></span></div>
        <div><ShieldAlert size={16} /><span>Operational priority<strong>{priority}</strong></span></div>
        <div className="exposure-action"><Info size={16} /><span>Recommended action<strong>{cell.recommended_action}</strong></span></div>
      </div>
      <div className="explanation-box"><Info size={17} /><p><strong>Why this risk?</strong>{cell.explanation}</p></div>
      <p className="mock-caveat">Potentially exposed means spatially intersecting a HIGH/SEVERE replay cell; field verification remains required.</p>
    </section>
  )
}
