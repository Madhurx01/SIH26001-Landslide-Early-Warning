import {
  historicalLandslides,
  sikkimBoundary,
} from '../data/mockRiskData'

const DEMO_DATE = '2021-10-19'
const dataUrl = (filename) => `${import.meta.env.BASE_URL}data/${filename}`

const fetchJson = async (filename) => {
  const response = await fetch(dataUrl(filename))
  if (!response.ok) throw new Error(`Unable to load ${filename}: ${response.status}`)
  return response.json()
}

const clampScore = (value) => Math.min(100, Math.max(0, Number(value)))
const triggerLevel = (score) => {
  if (score >= 70) return 'SEVERE'
  if (score >= 50) return 'HIGH'
  if (score >= 30) return 'MODERATE'
  return 'LOW'
}

const splitCellIds = (value) => String(value || '').split(';').map((item) => item.trim()).filter(Boolean)
const namedLocation = (entry) => [...entry.road_names, ...entry.settlement_names].join(' / ') || entry.cell_id

let dashboardPromise

const loadDashboard = () => {
  if (dashboardPromise) return dashboardPromise

  dashboardPromise = Promise.all([
    fetchJson('demo_risk.geojson'),
    fetchJson(`demo_dynamic_${DEMO_DATE}.json`),
    fetchJson(`dashboard_summary_${DEMO_DATE}.json`),
    fetchJson(`exposure_summary_${DEMO_DATE}.json`),
    fetchJson(`action_priority_${DEMO_DATE}.json`),
    fetchJson(`vehicular_road_exposure_${DEMO_DATE}.geojson`),
    fetchJson(`settlement_exposure_${DEMO_DATE}.geojson`),
  ]).then(([
    riskGeoJsonSource,
    dynamicArtifact,
    replaySummary,
    exposureSummary,
    actionPriority,
    roadGeoJson,
    settlementGeoJson,
  ]) => {
    const dynamicByCell = new Map(dynamicArtifact.records.map((record) => [record.cell_id, record]))
    const actionByCell = new Map(actionPriority.entries.map((entry) => [entry.cell_id, entry]))

    const riskCells = riskGeoJsonSource.features.map((feature) => {
      const properties = feature.properties
      const dynamic = dynamicByCell.get(properties.cell_id) || {}
      const action = actionByCell.get(properties.cell_id)
      const [longitude, latitude] = feature.geometry.coordinates
      const finalRiskScore = clampScore(properties.final_risk_score)
      const soilMoisture = dynamic.soil_moisture
      const roadNames = action?.road_names || []
      const settlementNames = action?.settlement_names || []

      return {
        cell_id: properties.cell_id,
        date: properties.date,
        latitude,
        longitude,
        static_susceptibility: clampScore(properties.static_susceptibility),
        dynamic_trigger_score: clampScore(dynamic.dynamic_trigger_score ?? properties.dynamic_trigger_score),
        final_risk_score: finalRiskScore,
        risk_level: properties.risk_level,
        rainfall_1d_mm: dynamic.rainfall_1d ?? null,
        rainfall_3d_mm: dynamic.rainfall_3d ?? null,
        rainfall_7d_mm: dynamic.rainfall_7d ?? null,
        soil_moisture_percent: soilMoisture == null ? null : Number(soilMoisture) * 100,
        road_names: roadNames,
        settlement_names: settlementNames,
        has_vehicular_road_exposure: Boolean(action?.has_vehicular_road_exposure),
        has_settlement_exposure: Boolean(action?.has_settlement_exposure),
        operational_priority: action?.priority ?? null,
        recommended_action: action?.recommended_action || 'No generated operational priority for this cell.',
        road_exposure_status: roadNames.length ? roadNames.join(', ') : 'No named vehicular road identified',
        settlement_exposure_status: settlementNames.length ? settlementNames.join(', ') : 'No mapped settlement identified',
        explanation: 'Operational index combines static susceptibility with rainfall and quality-filtered soil-moisture trigger signals for this historical replay.',
      }
    })

    const riskGeoJson = {
      type: 'FeatureCollection',
      features: riskGeoJsonSource.features.map((feature, index) => ({
        type: 'Feature',
        geometry: feature.geometry,
        properties: riskCells[index],
      })),
    }

    const roads = roadGeoJson.features.map((feature) => {
      const road = feature.properties
      const action = actionByCell.get(road.cell_id)
      return {
        osm_id: String(road.osm_id),
        road_id: `OSM ${road.osm_id}`,
        road_name: road.road_name || null,
        display_name: road.road_name || `Unnamed OSM road · ${road.osm_id}`,
        ref: road.ref || null,
        highway_type: road.highway_type,
        cell_id: road.cell_id,
        affected_cell_ids: splitCellIds(road.affected_cell_ids),
        risk_level: road.risk_level,
        maximum_risk_score: Number(road.final_risk_score),
        affected_length_km: Number(road.affected_length_km),
        priority: action?.priority ?? (road.risk_level === 'SEVERE' ? 1 : 2),
        recommended_action: action?.recommended_action || 'Field verification recommended; monitor rainfall and slope conditions.',
      }
    }).sort((left, right) => (
      left.priority - right.priority
      || Number(Boolean(right.road_name)) - Number(Boolean(left.road_name))
      || right.maximum_risk_score - left.maximum_risk_score
      || left.osm_id.localeCompare(right.osm_id)
    ))

    const settlements = settlementGeoJson.features.map((feature) => {
      const settlement = feature.properties
      return {
        settlement_id: `OSM ${settlement.osm_id}`,
        osm_id: String(settlement.osm_id),
        name: settlement.settlement_name,
        place_type: settlement.place_type,
        latitude: Number(settlement.latitude),
        longitude: Number(settlement.longitude),
        cell_id: settlement.cell_id,
        risk_level: settlement.risk_level,
        maximum_risk_score: Number(settlement.final_risk_score),
      }
    })

    const emergencyPriorities = exposureSummary.top_10_priority_locations.map((entry) => ({
      ...entry,
      location: namedLocation(entry),
      exposure: [
        entry.road_names.length ? `Road: ${entry.road_names.join(', ')}` : null,
        entry.settlement_names.length ? `Settlement: ${entry.settlement_names.join(', ')}` : null,
      ].filter(Boolean).join(' · '),
    }))

    const alerts = emergencyPriorities.slice(0, 5).map((entry, index) => ({
      alert_id: `PRI-${String(index + 1).padStart(3, '0')}`,
      risk_level: entry.risk_level,
      title: `${entry.risk_level} operational priority · ${entry.location}`,
      location_cell_id: entry.cell_id,
      detail: `${entry.exposure}. ${entry.recommended_action}`,
      channels: ['Operational dashboard', 'Field verification queue'],
    }))

    const weather = {
      rainfall_1d_mm: replaySummary.weather.rainfall_1d_median_mm,
      rainfall_3d_mm: replaySummary.weather.rainfall_3d_median_mm,
      rainfall_7d_mm: replaySummary.weather.rainfall_7d_median_mm,
      soil_moisture_percent: replaySummary.weather.soil_moisture_median == null
        ? null
        : replaySummary.weather.soil_moisture_median * 100,
      soil_moisture_valid_cells: replaySummary.weather.soil_moisture_valid_cells,
      dynamic_trigger_score: replaySummary.weather.dynamic_trigger_median,
      dynamic_trigger_level: triggerLevel(replaySummary.weather.dynamic_trigger_median),
      trigger_description: replaySummary.weather.trigger_description,
      scope_label: `Regional median across ${replaySummary.feature_count.toLocaleString('en-IN')} cells`,
    }

    const meta = {
      pilot_region: 'Sikkim, India',
      system_status: 'Replay Ready',
      last_updated: replaySummary.demo_date_display,
      data_mode: 'HISTORICAL REPLAY',
      demo_date: replaySummary.demo_date,
      demo_date_display: replaySummary.demo_date_display,
      feature_count: replaySummary.feature_count,
      priority_counts: {
        1: exposureSummary.priority_1_count,
        2: exposureSummary.priority_2_count,
        3: exposureSummary.priority_3_count,
      },
      summary: {
        severe_risk_cells: replaySummary.risk_counts.SEVERE,
        high_risk_cells: replaySummary.risk_counts.HIGH,
        roads_at_risk: exposureSummary.unique_named_roads,
        settlements_at_risk: exposureSummary.unique_exposed_settlements,
        weather_trigger: replaySummary.weather.trigger_description,
      },
    }

    const dataSources = [
      { source: 'SRTM DEM', status: 'REAL / Integrated', type: 'available' },
      { source: 'ESA WorldCover', status: 'REAL / Integrated', type: 'available' },
      { source: 'OSM Vehicular Roads', status: 'REAL / Exposure integrated', type: 'available' },
      { source: 'OSM Named Settlements', status: 'REAL / Exposure integrated', type: 'available' },
      { source: 'NASA GPM IMERG', status: 'REAL / Integrated', type: 'available' },
      { source: 'NASA SMAP', status: 'REAL / Integrated / quality filtered', type: 'available' },
      { source: 'GSI Historical Landslides', status: 'REAL / Integrated', type: 'available' },
    ]

    return {
      meta,
      riskCells,
      riskGeoJson,
      weather,
      roads,
      roadGeoJson,
      settlements,
      settlementGeoJson,
      historicalLandslides,
      sikkimBoundary,
      emergencyPriorities,
      actionPriorities: actionPriority.entries,
      exposureSummary,
      alerts,
      dataSources,
      modelInfo: replaySummary.model,
    }
  }).catch((error) => {
    dashboardPromise = undefined
    throw error
  })

  return dashboardPromise
}

export const api = {
  getDashboardMeta: () => loadDashboard().then((dashboard) => dashboard.meta),
  getRiskGrid: () => loadDashboard().then((dashboard) => dashboard.riskCells),
  getWeather: () => loadDashboard().then((dashboard) => dashboard.weather),
  getRoadRisk: () => loadDashboard().then((dashboard) => dashboard.roads),
  getAlerts: () => loadDashboard().then((dashboard) => dashboard.alerts),
  getEmergencyPriorities: () => loadDashboard().then((dashboard) => dashboard.emergencyPriorities),
  getSikkimBoundary: () => loadDashboard().then((dashboard) => dashboard.sikkimBoundary),
  getDashboard: loadDashboard,
}

export default api
