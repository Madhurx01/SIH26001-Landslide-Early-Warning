import { useMemo, useState } from 'react'
import { ChevronDown, Route } from 'lucide-react'
import SeverityBadge from './SeverityBadge'
import '../road-risk.css'

const riskRank = { LOW: 0, MODERATE: 1, HIGH: 2, SEVERE: 3 }
const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-IN')
const splitValues = (value) => String(value || '').split(';').map((item) => item.trim()).filter(Boolean)

const addValues = (target, value) => splitValues(value).forEach((item) => target.add(item))

function aggregateNamedRoads(roads) {
  const grouped = new Map()

  roads.forEach((road) => {
    if (!road.road_name) return

    // OSM roads are split into many ways and may carry different refs/classes
    // along one named physical road. The normalized name is the stable display
    // identity; all real refs and classes are retained on the grouped record.
    const identity = normalize(road.road_name)
    const existing = grouped.get(identity) || {
      identity,
      road_name: road.road_name.trim().replace(/\s+/g, ' '),
      refs: new Set(),
      classes: new Set(),
      risk_level: road.risk_level,
      maximum_risk_score: Number(road.maximum_risk_score),
      total_exposed_length_km: 0,
      exposed_segment_count: 0,
      priority: Number(road.priority),
      recommended_action: road.recommended_action,
      action_score: Number(road.maximum_risk_score),
    }

    addValues(existing.refs, road.ref)
    addValues(existing.classes, road.highway_type)
    existing.total_exposed_length_km += Number(road.affected_length_km)
    existing.exposed_segment_count += 1

    if (riskRank[road.risk_level] > riskRank[existing.risk_level]) {
      existing.risk_level = road.risk_level
    }
    existing.maximum_risk_score = Math.max(existing.maximum_risk_score, Number(road.maximum_risk_score))

    const roadPriority = Number(road.priority)
    const roadScore = Number(road.maximum_risk_score)
    if (roadPriority < existing.priority || (roadPriority === existing.priority && roadScore > existing.action_score)) {
      existing.priority = roadPriority
      existing.recommended_action = road.recommended_action
      existing.action_score = roadScore
    }

    grouped.set(identity, existing)
  })

  return [...grouped.values()]
    .map((road) => ({
      ...road,
      ref: [...road.refs].sort().join(' / '),
      road_class: [...road.classes].sort().join(', '),
    }))
    .sort((left, right) => (
      left.priority - right.priority
      || riskRank[right.risk_level] - riskRank[left.risk_level]
      || right.maximum_risk_score - left.maximum_risk_score
      || right.total_exposed_length_km - left.total_exposed_length_km
      || left.road_name.localeCompare(right.road_name)
    ))
}

function summarizeUnnamedRoads(roads) {
  const summaries = new Map()
  roads.filter((road) => !road.road_name).forEach((road) => {
    const roadClass = road.highway_type || 'unclassified'
    const current = summaries.get(roadClass) || { road_class: roadClass, segment_count: 0, exposed_length_km: 0 }
    current.segment_count += 1
    current.exposed_length_km += Number(road.affected_length_km)
    summaries.set(roadClass, current)
  })
  return [...summaries.values()].sort((left, right) => right.segment_count - left.segment_count || left.road_class.localeCompare(right.road_class))
}

export default function RoadRiskPanel({ roads, summary }) {
  const [showUnnamed, setShowUnnamed] = useState(false)
  const namedRoads = useMemo(() => aggregateNamedRoads(roads), [roads])
  const unnamedRoads = useMemo(() => summarizeUnnamedRoads(roads), [roads])
  const unnamedSegmentCount = roads.length - roads.filter((road) => road.road_name).length

  return (
    <section className="panel road-panel" id="road-risk">
      <div className="panel-heading">
        <div><span className="section-eyebrow"><Route size={14} /> REAL OSM VEHICULAR NETWORK</span><h2>Potential Road Exposure</h2><p>Road-level view aggregated from exposed OSM way segments</p></div>
        <div className="panel-heading-tags"><span className="workflow-label">REAL REPLAY · 19 OCT 2021</span><span className="record-count">{namedRoads.length} NAMED ROADS</span></div>
      </div>
      <div className="table-scroll road-table-scroll">
        <table>
          <thead><tr><th>Road</th><th>Reference</th><th>Road class</th><th>Maximum risk</th><th>Operational Risk Index</th><th>Total potentially exposed length</th><th>OSM segments</th><th>Priority</th><th>Recommended action</th></tr></thead>
          <tbody>{namedRoads.map((road) => (
            <tr key={road.identity}>
              <td><strong>{road.road_name}</strong></td>
              <td>{road.ref || '—'}</td>
              <td>{road.road_class || '—'}</td>
              <td><SeverityBadge level={road.risk_level} subtle /></td>
              <td>{road.maximum_risk_score.toFixed(1)} / 100</td>
              <td>{road.total_exposed_length_km.toFixed(3)} km</td>
              <td>{road.exposed_segment_count.toLocaleString('en-IN')}</td>
              <td><span className="road-priority">P{road.priority}</span></td>
              <td className="road-action-cell">{road.recommended_action}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <section className="unnamed-road-summary" aria-label="Unnamed vehicular road summary">
        <div>
          <strong>Unnamed/local vehicular ways: {unnamedSegmentCount.toLocaleString('en-IN')} exposed segments</strong>
          <span>Excluded from the primary named-road table to avoid hundreds of low-context OSM way rows.</span>
        </div>
        <button type="button" className="button-secondary" aria-expanded={showUnnamed} onClick={() => setShowUnnamed((current) => !current)}>
          {showUnnamed ? 'Hide' : 'Show'} unnamed road summary <ChevronDown size={15} className={showUnnamed ? 'is-open' : undefined} />
        </button>
        {showUnnamed && (
          <div className="unnamed-road-breakdown">
            {unnamedRoads.map((item) => (
              <div key={item.road_class}><span>{item.road_class}</span><strong>{item.segment_count.toLocaleString('en-IN')} segments</strong><small>{item.exposed_length_km.toFixed(3)} km potentially exposed</small></div>
            ))}
          </div>
        )}
      </section>
      <p className="panel-note">Potential exposure is based on spatial intersection with HIGH/SEVERE historical-replay risk cells and does not confirm road damage or closure.</p>
    </section>
  )
}
