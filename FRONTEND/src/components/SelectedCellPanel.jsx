import React from 'react'
import { ChevronDown, CloudRain, Droplets, Gauge, MapPinned, Mountain, Route, Ruler, Sparkles } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

function display(value, suffix = '') {
  return value === null || value === undefined ? 'Unavailable' : `${value}${suffix}`
}

function Metric({ icon: Icon, label, value }) {
  return <div className="detail-metric"><Icon size={16} /><span>{label}<strong>{value}</strong></span></div>
}

export default function SelectedCellPanel({ cell, telemetry }) {
  if (!cell) return null
  const index = Number(cell.operational_risk_index ?? 0)
  const factors = cell.risk_factors || []
  const liveSource = telemetry?.state === 'fresh'
    ? 'Open-Meteo model/API data'
    : cell.telemetry_source || 'Telemetry unavailable'
  const forecastRisk = [
    ['Next 24h', cell.operational_risk_index_24h, cell.risk_level_24h],
    ['Next 48h', cell.operational_risk_index_48h, cell.risk_level_48h],
    ['Next 72h', cell.operational_risk_index_72h, cell.risk_level_72h],
  ]

  return (
    <section className="panel selected-panel">
      <div className="panel-heading selected-heading">
        <div>
          <span className="section-eyebrow"><MapPinned size={14} /> SELECTED ANALYSIS CELL</span>
          <h2>{cell.cell_id}</h2>
        </div>
        <div className="selected-heading__status">
          <span>Current risk</span>
          <SeverityBadge level={cell.risk_level} />
        </div>
      </div>

      <div className="risk-score-block">
        <h3>Operational Risk Index</h3>
        <div className="risk-score">
          <div><strong>{index.toFixed(1)}</strong><span>/100</span></div>
          <span>Decision-support score</span>
        </div>
        <div className="risk-index-track">
          <span style={{ width: `${index}%`, background: index >= 75 ? '#d7191c' : index >= 50 ? '#e16713' : index >= 20 ? '#b87808' : '#27865f' }} />
        </div>
        <small>Static susceptibility + dynamic weather trigger · not a calibrated probability</small>
      </div>

      <div className="cell-priority-section">
        <div className="cell-section-heading">
          <h3>Decision snapshot</h3>
          <span>{liveSource}</span>
        </div>
        <div className="cell-key-grid">
          <Metric icon={CloudRain} label="Rainfall · prior 24h" value={display(cell.rainfall_1d_mm, ' mm')} />
          <Metric icon={Droplets} label="Soil moisture · VWC" value={display(cell.soil_moisture_vwc_percent, '%')} />
          <Metric icon={Ruler} label="Mean slope" value={display(cell.slope_deg, '°')} />
          <Metric icon={MapPinned} label="GEM fault distance" value={display(cell.distance_to_fault_km, ' km')} />
          <Metric icon={Sparkles} label="Sentinel-2 NDVI" value={display(cell.ndvi_mean)} />
          <Metric icon={Gauge} label="Dynamic trigger" value={display(cell.dynamic_trigger_index, '/100')} />
        </div>
        <div className="cell-proximity-grid">
          <div><Route size={16} /><span>Nearest mapped OSM road<strong>{display(cell.road_distance_m, ' m')}</strong></span></div>
          <div><MapPinned size={16} /><span>Nearest mapped settlement<strong>{cell.nearest_settlement || 'Unavailable'} · {display(cell.settlement_distance_m, ' m')}</strong></span></div>
        </div>
      </div>

      <div className="forecast-risk-block">
        <div className="cell-section-heading">
          <h3>Forecast-based risk</h3>
          <span>Model outlook</span>
        </div>
        <div className="forecast-risk-grid">
          {forecastRisk.map(([label, value, level]) => (
            <div className="forecast-risk-item" key={label}>
              <span>{label}</span>
              <strong>{display(value, '/100')}</strong>
              <SeverityBadge level={level} subtle />
            </div>
          ))}
        </div>
        <small>Forecast-based risk is a decision-support outlook, not a guaranteed event prediction.</small>
      </div>

      <div className="cell-support-sections">
        <details>
          <summary><span>Weather windows &amp; forecast inputs</span><ChevronDown size={16} /></summary>
          <div className="support-section-body">
            <div className="detail-metrics two-col">
              <Metric icon={CloudRain} label="Rainfall 3-day" value={display(cell.rainfall_3d_mm, ' mm')} />
              <Metric icon={CloudRain} label="Rainfall 7-day" value={display(cell.rainfall_7d_mm, ' mm')} />
              <Metric icon={CloudRain} label="Forecast rainfall 24h" value={display(cell.forecast_rainfall_24h_mm, ' mm')} />
              <Metric icon={CloudRain} label="Forecast rainfall 48h" value={display(cell.forecast_rainfall_48h_mm, ' mm')} />
              <Metric icon={CloudRain} label="Forecast rainfall 72h" value={display(cell.forecast_rainfall_72h_mm, ' mm')} />
            </div>
            <small>Spatial method: {cell.telemetry_location || 'Unavailable'}. Interpolated model/API data are not native 1 km observations.</small>
          </div>
        </details>

        <details>
          <summary><span>Risk factor context</span><ChevronDown size={16} /></summary>
          <div className="support-section-body risk-factor-list">
            {factors.length === 0 && <p>Factor details unavailable.</p>}
            {factors.map((factor) => (
              <div className={`risk-factor risk-factor--${factor.type || 'context'}`} key={`${factor.factor}-${factor.value}`}>
                <div><strong>{factor.factor}</strong><span>{factor.value}</span></div>
                <small>{factor.context}</small>
              </div>
            ))}
            <small>Contextual inputs only; these are not learned feature attributions.</small>
          </div>
        </details>

        <details>
          <summary><span>Technical context &amp; index rationale</span><ChevronDown size={16} /></summary>
          <div className="support-section-body">
            <Metric icon={Mountain} label="Mean elevation" value={display(cell.elevation_m, ' m')} />
            <div className="explanation-box"><p><strong>Index rationale</strong>{cell.explanation}</p></div>
            <p className="mock-caveat">Prototype decision-support index. Not a calibrated probability.</p>
          </div>
        </details>
      </div>
    </section>
  )
}
