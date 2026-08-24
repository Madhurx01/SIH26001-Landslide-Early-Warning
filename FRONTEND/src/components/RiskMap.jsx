import { useCallback, useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { Layers3, LocateFixed, Mountain } from 'lucide-react'
import { severityConfig } from '../data/mockRiskData'
import RiskLegend from './RiskLegend'

function MapFocus({ selectedCell }) {
  const map = useMap()
  const previousId = useRef(selectedCell?.cell_id)
  useEffect(() => {
    if (selectedCell && previousId.current !== selectedCell.cell_id) {
      map.flyTo([selectedCell.latitude, selectedCell.longitude], 12, { duration: 0.7 })
      previousId.current = selectedCell.cell_id
    }
  }, [map, selectedCell])
  return null
}

const layerLabels = {
  riskZones: 'Risk Zones · Real replay',
  roads: 'Potentially exposed vehicular roads · Real OSM',
  settlements: 'Potentially exposed settlements · Real OSM',
  history: 'Historical Landslides · Demo layer',
  boundary: 'Sikkim Boundary',
}

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]))

const markerForRiskFeature = (feature, latlng) => {
  const level = feature.properties.risk_level
  const config = severityConfig[level] || severityConfig.LOW
  const radius = { LOW: 2.4, MODERATE: 3.2, HIGH: 4.2, SEVERE: 5.2 }[level] || 2.4
  const fillOpacity = { LOW: 0.32, MODERATE: 0.55, HIGH: 0.72, SEVERE: 0.84 }[level] || 0.32
  return L.circleMarker(latlng, {
    radius,
    color: config.color,
    fillColor: config.color,
    fillOpacity,
    opacity: 0.9,
    weight: level === 'SEVERE' ? 1.2 : 0.7,
  })
}

const settlementMarker = (feature, latlng) => L.circleMarker(latlng, {
  radius: 5,
  color: '#fff',
  weight: 1.5,
  fillColor: feature.properties.risk_level === 'SEVERE' ? '#8b3f69' : '#174f8a',
  fillOpacity: 0.95,
})

export default function RiskMap({ riskGeoJson, roadGeoJson, settlementGeoJson, historicalLandslides, boundaryGeoJson, selectedCell, onSelectCell }) {
  const [layers, setLayers] = useState({ riskZones: true, roads: false, settlements: false, history: false, boundary: Boolean(boundaryGeoJson) })
  const [layersOpen, setLayersOpen] = useState(false)
  const toggleLayer = (key) => setLayers((current) => ({ ...current, [key]: !current[key] }))

  const bindRiskFeature = useCallback((feature, layer) => {
    const cell = feature.properties
    layer.bindTooltip(`${escapeHtml(cell.cell_id)} · ${cell.final_risk_score.toFixed(1)} / 100 · ${cell.risk_level}`, { direction: 'top', offset: [0, -5] })
    layer.bindPopup(`<div class="map-popup"><span>REAL REPLAY CELL · 19 OCT 2021</span><strong>${escapeHtml(cell.cell_id)}</strong><p><b>${cell.final_risk_score.toFixed(1)} / 100</b> operational risk index</p><small>${escapeHtml(cell.risk_level)}</small></div>`)
    layer.on('click', () => onSelectCell(cell))
  }, [onSelectCell])

  const bindRoadFeature = useCallback((feature, layer) => {
    const road = feature.properties
    const name = road.road_name || `Unnamed OSM road · ${road.osm_id}`
    layer.bindTooltip(`${escapeHtml(name)} · ${escapeHtml(road.risk_level)} · ${Number(road.affected_length_km).toFixed(3)} km potentially exposed`, { sticky: true })
  }, [])

  const bindSettlementFeature = useCallback((feature, layer) => {
    const settlement = feature.properties
    layer.bindTooltip(`${escapeHtml(settlement.settlement_name)} · ${escapeHtml(settlement.risk_level)} potential exposure`, { direction: 'right' })
  }, [])

  return (
    <section className="panel map-panel" id="risk-map">
      <div className="panel-heading map-heading">
        <div>
          <span className="section-eyebrow"><LocateFixed size={14} /> GIS RISK VISUALIZATION</span>
          <h2>Sikkim Landslide Risk Map</h2>
          <p>Real 7,390-cell pipeline output · historical replay for 19 Oct 2021</p>
        </div>
        <button className="layer-button" type="button" onClick={() => setLayersOpen(!layersOpen)} aria-expanded={layersOpen}>
          <Layers3 size={17} /> Layers <span>{Object.values(layers).filter(Boolean).length}/5</span>
        </button>
      </div>
      <div className="map-shell">
        {layersOpen && (
          <div className="layer-control">
            <strong>Map layers</strong>
            {Object.entries(layerLabels).map(([key, label]) => {
              const unavailable = key === 'boundary' && !boundaryGeoJson
              return (
                <label key={key} className={unavailable ? 'layer-unavailable' : undefined} title={unavailable ? 'Awaiting authoritative boundary GeoJSON from the API/data layer' : undefined}>
                  <input type="checkbox" checked={layers[key]} disabled={unavailable} onChange={() => toggleLayer(key)} />
                  <span>{label}{unavailable && <small>Awaiting GeoJSON</small>}</span>
                </label>
              )
            })}
          </div>
        )}
        <MapContainer center={[27.42, 88.50]} zoom={9} minZoom={8} scrollWheelZoom preferCanvas className="leaflet-map">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <MapFocus selectedCell={selectedCell} />
          {layers.boundary && boundaryGeoJson && (
            <GeoJSON key="sikkim-administrative-boundary" data={boundaryGeoJson} interactive={false} pathOptions={{ color: '#0b5964', weight: 3, opacity: 0.9, fillColor: '#0b5964', fillOpacity: 0.035, dashArray: '8 5' }} />
          )}
          {layers.riskZones && riskGeoJson && (
            <GeoJSON key="real-risk-grid-2021-10-19" data={riskGeoJson} pointToLayer={markerForRiskFeature} onEachFeature={bindRiskFeature} />
          )}
          {layers.roads && roadGeoJson && (
            <GeoJSON key="real-vehicular-road-exposure-2021-10-19" data={roadGeoJson} style={(feature) => ({ color: feature.properties.risk_level === 'SEVERE' ? '#b6232d' : '#e16713', weight: 2.5, opacity: 0.82 })} onEachFeature={bindRoadFeature} />
          )}
          {layers.settlements && settlementGeoJson && (
            <GeoJSON key="real-settlement-exposure-2021-10-19" data={settlementGeoJson} pointToLayer={settlementMarker} onEachFeature={bindSettlementFeature} />
          )}
          {layers.history && historicalLandslides.map((event) => (
            <CircleMarker key={event.event_id} center={[event.latitude, event.longitude]} radius={5} pathOptions={{ color: '#fff', weight: 2, fillColor: '#6e4b82', fillOpacity: 1 }}>
              <Tooltip><Mountain size={12} /> Demo layer · historical event {event.event_year}</Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
        <RiskLegend />
        <div className="map-demo-note">REAL MODEL + OSM EXPOSURE · HISTORICAL REPLAY · 19 OCT 2021</div>
      </div>
    </section>
  )
}
