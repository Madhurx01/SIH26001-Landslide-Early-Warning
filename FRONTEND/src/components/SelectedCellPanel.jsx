import React from 'react'
import { CloudRain, Droplets, Info, MapPinned, Mountain, Route, Ruler, Sparkles } from 'lucide-react'
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

  return (
    <section className="panel selected-panel">
      <div className="panel-heading selected-heading">
        <div>
          <span className="section-eyebrow"><MapPinned size={14} /> SELECTED ANALYSIS CELL</span>
          <h2>{cell.cell_id}</h2>
        </div>
        <SeverityBadge level={cell.risk_level} />
      </div>

      <div className="risk-score-block">
        <h3>Operational Risk Index</h3>
        <div className="risk-score"><strong>{index.toFixed(1)}</strong><span>Prototype score · 0–100</span></div>
        <div className="risk-index-track">
          <span style={{ width: `${index}%`, background: index >= 75 ? '#d7191c' : index >= 50 ? '#e16713' : index >= 20 ? '#b87808' : '#27865f' }} />
        </div>
        <small>Static susceptibility plus weather triggers · not a calibrated occurrence probability</small>
      </div>

      <div className="detail-section" style={{ background: '#f8fafc', borderRadius: '10px', padding: '0.85rem', border: '1px solid #e2e8f0', margin: '0.9rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <h3 style={{ margin: 0, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#1e293b' }}>
            <Sparkles size={15} color="#097969" /> Risk factor context
          </h3>
          <span style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 600 }}>CONTEXT ONLY</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
          {factors.length === 0 && <p>Factor details unavailable.</p>}
          {factors.map((factor) => {
            const color = factor.type === 'danger' ? '#e53e3e' : factor.type === 'warning' ? '#dd6b20' : '#319795'
            return (
              <div key={`${factor.factor}-${factor.value}`} style={{ fontSize: '0.78rem', borderLeft: `4px solid ${color}`, paddingLeft: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                  <strong style={{ color: '#334155' }}>{factor.factor}</strong>
                  <span style={{ color, fontWeight: 800 }}>{factor.value}</span>
                </div>
                <small style={{ color: '#64748b' }}>{factor.context}</small>
              </div>
            )
          })}
        </div>
      </div>

      <div className="detail-section">
        <h3>Real static inputs</h3>
        <div className="detail-metrics two-col">
          <Metric icon={Ruler} label="Mean slope" value={display(cell.slope_deg, '°')} />
          <Metric icon={Mountain} label="Mean elevation" value={display(cell.elevation_m, ' m')} />
          <Metric icon={MapPinned} label="GEM fault distance" value={display(cell.distance_to_fault_km, ' km')} />
          <Metric icon={Sparkles} label="Sentinel-2 NDVI" value={display(cell.ndvi_mean)} />
        </div>
      </div>

      <div className="detail-section">
        <h3>Weather trigger · {liveSource}</h3>
        <div className="detail-metrics two-col">
          <Metric icon={CloudRain} label="Rainfall 24h" value={display(cell.rainfall_1d_mm, ' mm')} />
          <Metric icon={CloudRain} label="Rainfall 3-day" value={display(cell.rainfall_3d_mm, ' mm')} />
          <Metric icon={CloudRain} label="Rainfall 7-day" value={display(cell.rainfall_7d_mm, ' mm')} />
          <Metric icon={Droplets} label="Soil moisture (VWC)" value={display(cell.soil_moisture_vwc_percent, '%')} />
        </div>
        <small>Nearest reference location: {cell.telemetry_location || 'Unavailable'}</small>
      </div>

      <div className="detail-section exposure-section">
        <h3>Static proximity context</h3>
        <div><Route size={16} /><span>Nearest mapped OSM road<strong>{display(cell.road_distance_m, ' m')}</strong></span></div>
        <div><MapPinned size={16} /><span>Nearest mapped settlement<strong>{cell.nearest_settlement || 'Unavailable'} · {display(cell.settlement_distance_m, ' m')}</strong></span></div>
      </div>

      <div className="explanation-box"><Info size={17} /><p><strong>Index rationale</strong>{cell.explanation}</p></div>
      <p className="mock-caveat">Prototype decision-support index. It is not a calibrated probability and the listed factors are contextual inputs, not learned feature attribution.</p>
    </section>
  )
}
