import { useEffect, useRef, useState } from 'react'
import { Circle, CircleMarker, GeoJSON, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { Layers3, LocateFixed, MapPin, Mountain, Route as RouteIcon } from 'lucide-react'
import { severityConfig } from '../data/mockRiskData'
import RiskLegend from './RiskLegend'
import SeverityBadge from './SeverityBadge'

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
  riskZones: 'Risk Zones',
  roads: 'Roads',
  settlements: 'Settlements',
  history: 'Historical Landslides',
  boundary: 'Sikkim Boundary',
}

export default function RiskMap({ riskCells, roads, settlements, historicalLandslides, boundaryGeoJson, selectedCell, onSelectCell }) {
  const [layers, setLayers] = useState({ riskZones: true, roads: true, settlements: true, history: false, boundary: Boolean(boundaryGeoJson) })
  const [layersOpen, setLayersOpen] = useState(false)

  const toggleLayer = (key) => setLayers((current) => ({ ...current, [key]: !current[key] }))

  return (
    <section className="panel map-panel" id="risk-map">
      <div className="panel-heading map-heading">
        <div>
          <span className="section-eyebrow"><LocateFixed size={14} /> GIS RISK VISUALIZATION</span>
          <h2>Sikkim Landslide Risk Map</h2>
          <p>Predicted risk, exposed routes and settlements · demonstration layers</p>
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
        <MapContainer center={[27.42, 88.50]} zoom={9} minZoom={8} scrollWheelZoom className="leaflet-map">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <MapFocus selectedCell={selectedCell} />
          {layers.boundary && boundaryGeoJson && (
            <GeoJSON
              key="sikkim-administrative-boundary"
              data={boundaryGeoJson}
              interactive={false}
              pathOptions={{ color: '#0b5964', weight: 3, opacity: 0.9, fillColor: '#0b5964', fillOpacity: 0.035, dashArray: '8 5' }}
            />
          )}
          {layers.riskZones && riskCells.map((cell) => {
            const config = severityConfig[cell.risk_level]
            const isSelected = selectedCell?.cell_id === cell.cell_id
            return (
              <Circle
                key={cell.cell_id}
                center={[cell.latitude, cell.longitude]}
                radius={cell.radius_m}
                pathOptions={{ color: isSelected ? '#102f38' : config.color, fillColor: config.color, fillOpacity: isSelected ? 0.72 : 0.48, weight: isSelected ? 3 : 2 }}
                eventHandlers={{ click: () => onSelectCell(cell) }}
              >
                <Tooltip direction="top" offset={[0, -8]}><strong>{cell.cell_id}</strong> · {cell.risk_probability}% {cell.risk_level}</Tooltip>
                <Popup>
                  <div className="map-popup">
                    <span>DEMO RISK CELL</span>
                    <strong>{cell.cell_id}</strong>
                    <SeverityBadge level={cell.risk_level} />
                    <p><b>{cell.risk_probability}%</b> predicted risk probability</p>
                    <button type="button" onClick={() => onSelectCell(cell)}>View assessment</button>
                  </div>
                </Popup>
              </Circle>
            )
          })}
          {layers.roads && roads.map((road) => (
            <Polyline key={road.road_id} positions={road.coordinates} pathOptions={{ color: road.risk_level === 'SEVERE' ? '#b6232d' : '#304a54', weight: 4, opacity: 0.88, dashArray: road.risk_level === 'MODERATE' ? '7 6' : undefined }}>
              <Tooltip sticky><RouteIcon size={12} /> {road.road_name} · {road.status}</Tooltip>
            </Polyline>
          ))}
          {layers.settlements && settlements.map((settlement) => (
            <CircleMarker key={settlement.settlement_id} center={[settlement.latitude, settlement.longitude]} radius={6} pathOptions={{ color: '#fff', weight: 2, fillColor: '#174f8a', fillOpacity: 1 }}>
              <Tooltip direction="right"><MapPin size={12} /> {settlement.name}<br />Potential exposure: {settlement.population_exposure}</Tooltip>
            </CircleMarker>
          ))}
          {layers.history && historicalLandslides.map((event) => (
            <CircleMarker key={event.event_id} center={[event.latitude, event.longitude]} radius={5} pathOptions={{ color: '#fff', weight: 2, fillColor: '#6e4b82', fillOpacity: 1 }}>
              <Tooltip><Mountain size={12} /> Historical event {event.event_year}<br />{event.source_status}</Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
        <RiskLegend />
        <div className="map-demo-note">DEMONSTRATION LAYERS — NOT OPERATIONAL DATA</div>
      </div>
    </section>
  )
}
