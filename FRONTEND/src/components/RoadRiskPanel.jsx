import React, { useMemo, useState } from 'react'
import { Route, ExternalLink, Search } from 'lucide-react'
import SeverityBadge from './SeverityBadge'

const statusClass = (status) => status.toLowerCase().replaceAll(' ', '-')
const TOP_ROAD_LIMIT = 15
const STATUS_PRIORITY = {
  CRITICAL: 0,
  'HIGH RISK': 1,
  WATCH: 2,
  NORMAL: 3,
}

const hasOsmNameOrRef = (road) => Boolean(road.source_ref || road.source_name)

const compareOperationalImportance = (left, right) => {
  const statusDifference = (STATUS_PRIORITY[left.status] ?? 99) - (STATUS_PRIORITY[right.status] ?? 99)
  if (statusDifference !== 0) return statusDifference

  const severeDifference = (right.current_exposure?.severe_cell_count ?? 0) - (left.current_exposure?.severe_cell_count ?? 0)
  if (severeDifference !== 0) return severeDifference

  const taggedDifference = Number(hasOsmNameOrRef(right)) - Number(hasOsmNameOrRef(left))
  if (taggedDifference !== 0) return taggedDifference

  const lengthDifference = (Number(right.affected_segment_km) || 0) - (Number(left.affected_segment_km) || 0)
  if (lengthDifference !== 0) return lengthDifference

  return String(left.road_name).localeCompare(String(right.road_name))
}

export default function RoadRiskPanel({ roads, exposureMeta, onInspectRoad }) {
  const [showAll, setShowAll] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const rankedRoads = useMemo(
    () => [...roads].sort(compareOperationalImportance),
    [roads],
  )

  const normalizedQuery = searchQuery.trim().toLocaleLowerCase()
  const matchingRoads = useMemo(() => {
    if (!normalizedQuery) return rankedRoads

    return rankedRoads.filter((road) => (
      [road.road_name, road.source_ref, road.source_name]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase().includes(normalizedQuery))
    ))
  }, [normalizedQuery, rankedRoads])

  const displayedRoads = normalizedQuery
    ? matchingRoads
    : (showAll ? rankedRoads : rankedRoads.slice(0, TOP_ROAD_LIMIT))

  return (
    <section className="panel road-panel">
      <div className="panel-heading">
        <div>
          <span className="section-eyebrow"><Route size={14} /> TRANSPORT NETWORK</span>
          <h2>GIS Road Exposure</h2>
          <p>Exact OSM road intersections with current and forecast HIGH/SEVERE 1 km cells</p>
        </div>
        <span className="record-count">{displayedRoads.length} DISPLAYED · {roads.length} AVAILABLE</span>
      </div>
      <div className="road-table-controls">
        <label className="road-search" htmlFor="road-exposure-search">
          <Search size={14} aria-hidden="true" />
          <input
            id="road-exposure-search"
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search road name or reference"
            aria-label="Search exposed roads by name or reference"
          />
        </label>
        <button
          type="button"
          className="button-secondary road-table-toggle"
          onClick={() => setShowAll((current) => !current)}
        >
          {showAll ? `Show top ${TOP_ROAD_LIMIT}` : `Show all exposed roads (${roads.length})`}
        </button>
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
            {displayedRoads.map((road) => (
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
            {displayedRoads.length === 0 && (
              <tr>
                <td className="road-table-empty" colSpan="7">No road name or reference matches this search.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="panel-note">Potential GIS exposure only—not a confirmed blockage. Unnamed roads retain their OSM identity; no corridor names, blockage states, or detours are invented. The audit CSV covers all {exposureMeta?.road_feature_count ?? '—'} processed road features.</p>
    </section>
  )
}
