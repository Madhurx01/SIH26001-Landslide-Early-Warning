import { Component, useCallback, useEffect, useRef, useState } from 'react'
import { Circle, CircleMarker, GeoJSON, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { AlertTriangle, Layers3, LoaderCircle, LocateFixed, MapPin, Mountain, Route as RouteIcon } from 'lucide-react'
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

function MapSizeManager({ refreshKey, onReady }) {
  const map = useMap()

  useEffect(() => {
    const invalidate = () => map.invalidateSize({ animate: false, pan: false })
    const frame = window.requestAnimationFrame(() => {
      invalidate()
      onReady()
    })
    const delayed = window.setTimeout(invalidate, 240)
    const container = map.getContainer()
    const resizeObserver = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(() => window.requestAnimationFrame(invalidate))

    resizeObserver?.observe(container)
    window.addEventListener('resize', invalidate)
    const handleVisibility = () => {
      if (!document.hidden) window.requestAnimationFrame(invalidate)
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(delayed)
      resizeObserver?.disconnect()
      window.removeEventListener('resize', invalidate)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [map, onReady])

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => map.invalidateSize({ animate: false, pan: false }))
    return () => window.cancelAnimationFrame(frame)
  }, [map, refreshKey])

  return null
}

class MapErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidUpdate(previousProps) {
    if (this.state.failed && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ failed: false })
    }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

function MapFallback({ title, message }) {
  return (
    <div className="map-fallback" role="status">
      <span className="map-fallback__icon"><AlertTriangle size={22} /></span>
      <strong>{title}</strong>
      <p>{message}</p>
      <small>Try switching dashboard mode or refreshing the page. The selected-cell assessment remains available.</small>
    </div>
  )
}

const layerLabels = {
  riskZones: 'Risk Zones',
  roads: 'Roads',
  settlements: 'Settlements',
  history: 'Historical Landslides',
  boundary: 'Sikkim Boundary',
}

export default function RiskMap({ riskCells = [], roads = [], settlements = [], historicalLandslides = [], boundaryGeoJson, selectedCell, onSelectCell }) {
  const [layers, setLayers] = useState({ riskZones: true, roads: true, settlements: true, history: false, boundary: Boolean(boundaryGeoJson) })
  const [layersOpen, setLayersOpen] = useState(false)
  const [mapReady, setMapReady] = useState(false)
  const [tileWarning, setTileWarning] = useState(false)

  const toggleLayer = (key) => setLayers((current) => ({ ...current, [key]: !current[key] }))
  const handleMapReady = useCallback(() => setMapReady(true), [])
  const hasRiskData = riskCells.length > 0
  const mapResetKey = `${riskCells.length}:${roads.length}:${selectedCell?.cell_id || 'none'}`
  const mapRefreshKey = `${mapResetKey}:${layersOpen}:${Object.values(layers).join('-')}`

  return (
    <section className="panel map-panel" id="risk-map">
      <div className="panel-heading map-heading">
        <div>
          <span className="section-eyebrow"><LocateFixed size={14} /> GIS RISK VISUALIZATION</span>
          <h2>Sikkim Landslide Risk Map</h2>
          <p>Prototype Operational Risk Index with static context · 1-km analysis grid</p>
        </div>
        <button className="layer-button" type="button" onClick={() => setLayersOpen(!layersOpen)} aria-expanded={layersOpen}>
          <Layers3 size={17} /> Layers <span>{Object.values(layers).filter(Boolean).length}/5</span>
        </button>
      </div>
      <div className="map-shell">
        {hasRiskData && layersOpen && (
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
        {!hasRiskData ? (
          <MapFallback title="Risk map data unavailable" message="No canonical risk cells were supplied for this dashboard view." />
        ) : (
          <MapErrorBoundary
            resetKey={mapResetKey}
            fallback={<MapFallback title="Map could not be rendered" message="The GIS view encountered a display error; no risk values were changed." />}
          >
            <MapContainer center={[27.42, 88.50]} zoom={9} minZoom={8} scrollWheelZoom preferCanvas className="leaflet-map">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                eventHandlers={{ tileerror: () => setTileWarning(true), load: () => setTileWarning(false) }}
              />
              <MapFocus selectedCell={selectedCell} />
              <MapSizeManager refreshKey={mapRefreshKey} onReady={handleMapReady} />
              {layers.boundary && boundaryGeoJson && (
                <GeoJSON
                  key="sikkim-administrative-boundary"
                  data={boundaryGeoJson}
                  interactive={false}
                  pathOptions={{ color: '#0b5964', weight: 3, opacity: 0.9, fillColor: '#0b5964', fillOpacity: 0.035, dashArray: '8 5' }}
                />
              )}
              {layers.riskZones && riskCells.map((cell) => {
                const config = severityConfig[cell.risk_level] || severityConfig.MODERATE
                const isSelected = selectedCell?.cell_id === cell.cell_id
                return (
                  <Circle
                    key={cell.cell_id}
                    center={[cell.latitude, cell.longitude]}
                    radius={cell.radius_m}
                    pathOptions={{ color: isSelected ? '#102f38' : config.color, fillColor: config.color, fillOpacity: isSelected ? 0.72 : 0.48, weight: isSelected ? 3 : 2 }}
                    eventHandlers={{ click: () => onSelectCell(cell) }}
                  >
                    <Tooltip direction="top" offset={[0, -8]}><strong>{cell.cell_id}</strong> · index {cell.operational_risk_index} {cell.risk_level}</Tooltip>
                    <Popup>
                      <div className="map-popup">
                        <span>OPERATIONAL INDEX CELL</span>
                        <strong>{cell.cell_id}</strong>
                        <SeverityBadge level={cell.risk_level} />
                        <p><b>{cell.operational_risk_index}/100</b> prototype decision-support index</p>
                        <button type="button" onClick={() => onSelectCell(cell)}>View assessment</button>
                      </div>
                    </Popup>
                  </Circle>
                )
              })}
              {layers.roads && roads.map((road) => (
                <Polyline key={road.road_id} positions={road.coordinates} pathOptions={{ color: road.status === 'CRITICAL' ? '#b6232d' : road.status === 'HIGH RISK' ? '#e16713' : road.status === 'WATCH' ? '#b87808' : '#304a54', weight: 4, opacity: 0.88, dashArray: road.status === 'WATCH' ? '7 6' : undefined }}>
                  <Tooltip sticky><RouteIcon size={12} /> {road.road_name} · {road.status}<br />Potentially exposed: {road.current_exposure?.exposed_cell_count ?? 0} cells / {road.affected_segment_km} km</Tooltip>
                </Polyline>
              ))}
              {layers.settlements && settlements.map((settlement) => (
                <CircleMarker key={settlement.settlement_id} center={[settlement.latitude, settlement.longitude]} radius={6} pathOptions={{ color: '#fff', weight: 2, fillColor: settlement.risk_level === 'SEVERE' ? '#b6232d' : settlement.risk_level === 'HIGH' ? '#e16713' : '#174f8a', fillOpacity: 1 }}>
                  <Tooltip direction="right"><MapPin size={12} /> {settlement.name} · {settlement.settlement_type}<br />Current: {settlement.operational_risk_index} {settlement.risk_level}<br />Forecast 24/48/72h: {settlement.operational_risk_index_24h} / {settlement.operational_risk_index_48h} / {settlement.operational_risk_index_72h}</Tooltip>
                </CircleMarker>
              ))}
              {layers.history && historicalLandslides.map((event) => (
                <CircleMarker key={event.event_id} center={[event.latitude, event.longitude]} radius={5} pathOptions={{ color: '#fff', weight: 2, fillColor: '#6e4b82', fillOpacity: 1 }}>
                  <Tooltip><Mountain size={12} /> Historical event {event.event_year}<br />{event.source_status}</Tooltip>
                </CircleMarker>
              ))}
            </MapContainer>
            {!mapReady && <div className="map-loading"><LoaderCircle size={22} /><strong>Rendering GIS layers</strong><span>Preparing the canonical 1 km risk grid…</span></div>}
            {tileWarning && <div className="map-network-note">Basemap tiles are unavailable; operational overlays remain visible.</div>}
            <RiskLegend />
            <div className="map-demo-note">PROTOTYPE OPERATIONAL RISK INDEX · NOT A CALIBRATED PROBABILITY</div>
          </MapErrorBoundary>
        )}
      </div>
    </section>
  )
}
