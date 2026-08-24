import { Route } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

const statusClass = (status) => status.toLowerCase().replaceAll(' ', '-')

export default function RoadRiskPanel({ roads }) {
  return (
    <section className="panel road-panel">
      <div className="panel-heading">
        <div><span className="section-eyebrow"><Route size={14} /> TRANSPORT NETWORK</span><h2>Road Connectivity & Risk</h2><p>Potential exposure from demonstration risk overlays</p></div>
        <span className="record-count">{roads.length} PRIORITY SEGMENTS</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Road</th><th>Risk level</th><th>Affected segment</th><th>Nearby settlement</th><th>Status</th></tr></thead>
          <tbody>{roads.map((road) => (
            <tr key={road.road_id}>
              <td><strong>{road.road_name}</strong><small>{road.road_id}</small></td>
              <td><SeverityBadge level={road.risk_level} subtle /></td>
              <td>{road.affected_segment_km} km</td>
              <td>{road.nearby_settlement}</td>
              <td><span className={`road-status road-status--${statusClass(road.status)}`}>{road.status}</span></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="panel-note">Statuses indicate potential movement risk only. They do not confirm an actual road closure.</p>
    </section>
  )
}
