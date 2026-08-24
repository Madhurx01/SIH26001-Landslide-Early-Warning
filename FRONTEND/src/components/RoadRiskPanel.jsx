import React from 'react'
import { Route, Search, ExternalLink } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

const statusClass = (status) => status.toLowerCase().replaceAll(' ', '-')

export default function RoadRiskPanel({ roads, onInspectRoad }) {
  return (
    <section className="panel road-panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow"><Route size={14} /> TRANSPORT NETWORK</span>
          <h2>Road Connectivity &amp; Risk</h2>
          <p>Click any corridor below to open the <strong>Highway Lifeline Inspector</strong> with chokepoints &amp; detour routes</p>
        </div>
        <span className="record-count">{roads.length} STRATEGIC CORRIDORS</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Road Corridor</th>
              <th>Risk Level</th>
              <th>Affected Stretch</th>
              <th>Key Hotspot</th>
              <th>Movement Status</th>
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
                  <small>{road.road_id}</small>
                </td>
                <td><SeverityBadge level={road.risk_level} subtle /></td>
                <td><strong>{road.affected_segment_km} km</strong> <small style={{ color: '#888' }}>({road.total_length_km ? `${road.total_length_km}km tot` : ''})</small></td>
                <td>{road.nearby_settlement}</td>
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
      <p className="panel-note">Statuses indicate potential movement risk only. Click any road to inspect chokepoint telemetry and alternate diversion axes.</p>
    </section>
  )
}
