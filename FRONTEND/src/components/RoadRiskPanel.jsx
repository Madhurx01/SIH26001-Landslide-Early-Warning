import React from 'react'
import { Route, ExternalLink } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

const statusClass = (status) => status.toLowerCase().replaceAll(' ', '-')

export default function RoadRiskPanel({ roads, exposureMeta, onInspectRoad }) {
  return (
    <section className="panel road-panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow"><Route size={14} /> TRANSPORT NETWORK</span>
          <h2>GIS Road Exposure</h2>
          <p>Exact OSM road intersections with current and forecast HIGH/SEVERE 1 km cells</p>
        </div>
        <span className="record-count">{roads.length} DISPLAYED · {exposureMeta?.road_entities_exposed_current ?? '—'} EXPOSED</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>OSM road / segment</th>
              <th>Current risk</th>
              <th>Exposed cells</th>
              <th>Exposed length</th>
              <th>Forecast 24 / 48 / 72h</th>
              <th>Operational status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {roads.map((road) => (
              <tr
                key={road.road_id}
                onClick={() => onInspectRoad && onInspectRoad(road)}
                style={{ cursor: 'pointer', transition: 'background 0.15s ease' }}
                className="road-row-hover"
              >
                <td>
                  <strong>{road.road_name}</strong>
                  <small>{road.source_ref || road.source_name || road.road_id} · {road.road_classes?.join(', ')}</small>
                </td>
                <td><SeverityBadge level={road.risk_level} subtle /></td>
                <td><strong>{road.current_exposure?.exposed_cell_count ?? 0}</strong> <small>({road.current_exposure?.high_cell_count ?? 0} HIGH · {road.current_exposure?.severe_cell_count ?? 0} SEVERE)</small></td>
                <td><strong>{road.affected_segment_km} km</strong> <small style={{ color: '#888' }}>of {road.total_length_km} km mapped</small></td>
                <td><strong>{road.forecast_exposure_24h?.exposed_cell_count ?? 0}</strong> / <strong>{road.forecast_exposure_48h?.exposed_cell_count ?? 0}</strong> / <strong>{road.forecast_exposure_72h?.exposed_cell_count ?? 0}</strong> cells</td>
                <td><span className={`road-status road-status--${statusClass(road.status)}`}>{road.status}</span></td>
                <td>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (onInspectRoad) onInspectRoad(road)
                    }}
                    style={{
                      background: '#0a3d46',
                      color: '#26d0ce',
                      border: '1px solid #138b9c',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}
                  >
                    Inspect <ExternalLink size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="panel-note">Potential GIS exposure only—not a confirmed blockage. Unnamed roads retain their OSM identity; no corridor names, blockage states, or detours are invented. The audit CSV covers all {exposureMeta?.road_feature_count ?? '—'} processed road features.</p>
    </section>
  )
}
