export const severityConfig = {
  LOW: { color: '#27865f', fill: '#d8f3e5', label: 'Low' },
  MODERATE: { color: '#b87808', fill: '#fff0c2', label: 'Moderate' },
  HIGH: { color: '#e16713', fill: '#ffe3cf', label: 'High' },
  SEVERE: { color: '#c7353f', fill: '#ffe0e2', label: 'Severe' },
}

export const dashboardMeta = {
  pilot_region: 'Sikkim, India',
  system_status: 'Monitoring',
  last_updated: '24 Aug 2026, 10:30 IST',
  data_mode: 'DEMO / LIVE-ready',
  summary: {
    severe_risk_cells: 8,
    high_risk_cells: 21,
    roads_at_risk: 12,
    settlements_at_risk: 5,
    weather_trigger: 'Heavy Rainfall',
  },
}

export const riskCells = [
  {
    cell_id: 'SKM_042', latitude: 27.315, longitude: 88.596, radius_m: 760,
    risk_probability: 84, risk_level: 'SEVERE', elevation_m: 2150, slope_deg: 43,
    rainfall_1d_mm: 92, rainfall_3d_mm: 184, rainfall_7d_mm: 263, soil_moisture: 78,
    nearest_road: 'NH-10', road_distance_m: 120, nearest_settlement: 'Demo Settlement A', settlement_distance_m: 650,
    explanation: 'High predicted risk due to steep terrain, accumulated rainfall and saturated soil.',
  },
  {
    cell_id: 'SKM_018', latitude: 27.533, longitude: 88.512, radius_m: 670,
    risk_probability: 76, risk_level: 'HIGH', elevation_m: 1780, slope_deg: 38,
    rainfall_1d_mm: 78, rainfall_3d_mm: 152, rainfall_7d_mm: 224, soil_moisture: 72,
    nearest_road: 'North Sikkim Highway', road_distance_m: 280, nearest_settlement: 'Demo Settlement B', settlement_distance_m: 900,
    explanation: 'Elevated predicted risk from persistent rainfall on a steep, moisture-rich slope.',
  },
  {
    cell_id: 'SKM_067', latitude: 27.168, longitude: 88.363, radius_m: 720,
    risk_probability: 69, risk_level: 'HIGH', elevation_m: 1460, slope_deg: 35,
    rainfall_1d_mm: 71, rainfall_3d_mm: 143, rainfall_7d_mm: 205, soil_moisture: 68,
    nearest_road: 'State Road 04', road_distance_m: 190, nearest_settlement: 'Demo Settlement C', settlement_distance_m: 520,
    explanation: 'Predicted risk is driven by recent rainfall accumulation and steep local terrain.',
  },
  {
    cell_id: 'SKM_073', latitude: 27.239, longitude: 88.411, radius_m: 560,
    risk_probability: 61, risk_level: 'HIGH', elevation_m: 1640, slope_deg: 34,
    rainfall_1d_mm: 64, rainfall_3d_mm: 131, rainfall_7d_mm: 191, soil_moisture: 65,
    nearest_road: 'Local Road 12', road_distance_m: 310, nearest_settlement: 'Demo Settlement D', settlement_distance_m: 740,
    explanation: 'High predicted risk based on rainfall persistence, slope and soil moisture signals.',
  },
  {
    cell_id: 'SKM_026', latitude: 27.603, longitude: 88.645, radius_m: 620,
    risk_probability: 55, risk_level: 'MODERATE', elevation_m: 2380, slope_deg: 31,
    rainfall_1d_mm: 51, rainfall_3d_mm: 108, rainfall_7d_mm: 167, soil_moisture: 59,
    nearest_road: 'District Road 07', road_distance_m: 410, nearest_settlement: 'Demo Settlement E', settlement_distance_m: 1050,
    explanation: 'Moderate predicted risk with rainfall and terrain indicators requiring continued monitoring.',
  },
  {
    cell_id: 'SKM_031', latitude: 27.435, longitude: 88.603, radius_m: 530,
    risk_probability: 48, risk_level: 'MODERATE', elevation_m: 1930, slope_deg: 29,
    rainfall_1d_mm: 46, rainfall_3d_mm: 96, rainfall_7d_mm: 151, soil_moisture: 57,
    nearest_road: 'NH-10', road_distance_m: 360, nearest_settlement: 'Demo Settlement F', settlement_distance_m: 880,
    explanation: 'Moderate predicted risk due to wet antecedent conditions on sloping terrain.',
  },
  {
    cell_id: 'SKM_081', latitude: 27.087, longitude: 88.503, radius_m: 590,
    risk_probability: 44, risk_level: 'MODERATE', elevation_m: 1220, slope_deg: 27,
    rainfall_1d_mm: 43, rainfall_3d_mm: 91, rainfall_7d_mm: 144, soil_moisture: 54,
    nearest_road: 'State Road 02', road_distance_m: 480, nearest_settlement: 'Demo Settlement G', settlement_distance_m: 980,
    explanation: 'Moderate predicted risk; continued rainfall could increase local slope susceptibility.',
  },
  {
    cell_id: 'SKM_012', latitude: 27.716, longitude: 88.561, radius_m: 680,
    risk_probability: 37, risk_level: 'MODERATE', elevation_m: 2860, slope_deg: 26,
    rainfall_1d_mm: 39, rainfall_3d_mm: 82, rainfall_7d_mm: 133, soil_moisture: 51,
    nearest_road: 'North Sikkim Highway', road_distance_m: 520, nearest_settlement: 'Demo Settlement H', settlement_distance_m: 1250,
    explanation: 'Moderate predicted risk from accumulated rainfall with no severe trigger indicated in demo data.',
  },
  {
    cell_id: 'SKM_093', latitude: 27.128, longitude: 88.287, radius_m: 500,
    risk_probability: 24, risk_level: 'LOW', elevation_m: 1180, slope_deg: 18,
    rainfall_1d_mm: 25, rainfall_3d_mm: 61, rainfall_7d_mm: 102, soil_moisture: 42,
    nearest_road: 'Local Road 05', road_distance_m: 690, nearest_settlement: 'Demo Settlement I', settlement_distance_m: 1370,
    explanation: 'Low predicted risk in the current demo scenario, with routine monitoring advised.',
  },
  {
    cell_id: 'SKM_055', latitude: 27.382, longitude: 88.347, radius_m: 540,
    risk_probability: 18, risk_level: 'LOW', elevation_m: 1560, slope_deg: 16,
    rainfall_1d_mm: 22, rainfall_3d_mm: 54, rainfall_7d_mm: 94, soil_moisture: 39,
    nearest_road: 'District Road 03', road_distance_m: 740, nearest_settlement: 'Demo Settlement J', settlement_distance_m: 1420,
    explanation: 'Low predicted risk based on the current demonstration trigger values.',
  },
]

export const weather = {
  current_rainfall_mm_hr: 8.4,
  rainfall_1d_mm: 92,
  rainfall_3d_mm: 184,
  rainfall_7d_mm: 263,
  soil_moisture_percent: 78,
  next_24h_risk: 'HIGH',
  trend: [
    { time: '06:00', value: 3.2 }, { time: '09:00', value: 5.8 },
    { time: '12:00', value: 8.4 }, { time: '15:00', value: 11.2 },
    { time: '18:00', value: 7.6 }, { time: '21:00', value: 4.9 },
  ],
}

export const roads = [
  { road_id: 'R-01', road_name: 'NH-10', risk_level: 'SEVERE', affected_segment_km: 2.3, nearby_settlement: 'Demo Village A', status: 'MOVEMENT AT RISK', coordinates: [[27.105, 88.493], [27.208, 88.529], [27.315, 88.596], [27.43, 88.604]] },
  { road_id: 'R-02', road_name: 'State Road 04', risk_level: 'HIGH', affected_segment_km: 1.1, nearby_settlement: 'Demo Village B', status: 'CAUTION', coordinates: [[27.12, 88.31], [27.168, 88.363], [27.239, 88.411]] },
  { road_id: 'R-03', road_name: 'Local Road 12', risk_level: 'MODERATE', affected_segment_km: 0.6, nearby_settlement: 'Demo Village C', status: 'OPEN', coordinates: [[27.22, 88.39], [27.239, 88.411], [27.27, 88.45]] },
  { road_id: 'R-04', road_name: 'North Sikkim Highway', risk_level: 'HIGH', affected_segment_km: 1.7, nearby_settlement: 'Demo Village D', status: 'POTENTIAL BLOCKAGE', coordinates: [[27.43, 88.57], [27.533, 88.512], [27.64, 88.54], [27.716, 88.561]] },
]

export const settlements = [
  { settlement_id: 'S-01', name: 'Demo Village A', latitude: 27.321, longitude: 88.589, population_exposure: 420 },
  { settlement_id: 'S-02', name: 'Demo Village B', latitude: 27.176, longitude: 88.355, population_exposure: 280 },
  { settlement_id: 'S-03', name: 'Demo Village C', latitude: 27.247, longitude: 88.423, population_exposure: 165 },
  { settlement_id: 'S-04', name: 'Demo Village D', latitude: 27.542, longitude: 88.521, population_exposure: 310 },
  { settlement_id: 'S-05', name: 'Demo Village E', latitude: 27.611, longitude: 88.634, population_exposure: 120 },
]

export const historicalLandslides = [
  { event_id: 'HL-01', latitude: 27.294, longitude: 88.584, event_year: 2018, source_status: 'Demo location' },
  { event_id: 'HL-02', latitude: 27.519, longitude: 88.499, event_year: 2020, source_status: 'Demo location' },
  { event_id: 'HL-03', latitude: 27.154, longitude: 88.349, event_year: 2022, source_status: 'Demo location' },
  { event_id: 'HL-04', latitude: 27.414, longitude: 88.594, event_year: 2019, source_status: 'Demo location' },
]

// Intentionally null until an authoritative Sikkim administrative boundary
// GeoJSON is supplied by the GIS/API integration. Do not substitute mock geometry.
export const sikkimBoundary = null

export const emergencyPriorities = [
  { priority: 1, risk_level: 'SEVERE', location: 'SKM_042 / NH-10', exposure: 'Road + populated settlement', reason: 'Steep terrain with high rainfall accumulation and settlement exposure.', recommended_action: 'Issue warning and deploy field verification team.' },
  { priority: 2, risk_level: 'HIGH', location: 'SKM_018 / North Sikkim Highway', exposure: 'Major road', reason: 'Persistent rainfall may affect a strategic road segment.', recommended_action: 'Verify road condition and prepare temporary traffic restriction.' },
  { priority: 3, risk_level: 'HIGH', location: 'SKM_067 / Demo Village B', exposure: 'Small settlement', reason: 'High predicted risk within the settlement monitoring radius.', recommended_action: 'Alert local officials and monitor rainfall.' },
]

export const alerts = [
  { alert_id: 'ALT-001', risk_level: 'SEVERE', title: 'High landslide probability near NH-10 demo segment', location_cell_id: 'SKM_042', detail: 'Risk signals exceed the current demonstration threshold.', channels: ['SMS', 'App Notification', 'Community Alert'] },
  { alert_id: 'ALT-002', risk_level: 'HIGH', title: 'Increasing rainfall accumulation in northern monitoring zone', location_cell_id: 'SKM_018', detail: 'Three-day rainfall accumulation is trending upward in demo data.', channels: ['App Notification', 'Community Alert'] },
]

export const dataSources = [
  { source: 'Terrain / DEM', status: 'Available', type: 'available' },
  { source: 'Land Cover', status: 'Available', type: 'available' },
  { source: 'Road & Settlement GIS', status: 'Available', type: 'available' },
  { source: 'Rainfall', status: 'Demo / Integration Pending', type: 'demo' },
  { source: 'Soil Moisture', status: 'Demo / Integration Pending', type: 'demo' },
  { source: 'Historical Landslides', status: 'Integration Pending', type: 'pending' },
]

export const mockDashboardData = {
  meta: dashboardMeta,
  riskCells,
  weather,
  roads,
  settlements,
  historicalLandslides,
  sikkimBoundary,
  emergencyPriorities,
  alerts,
  dataSources,
}
