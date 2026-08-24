export const severityConfig = {
  LOW: { color: '#27865f', fill: '#d8f3e5', label: 'Low' },
  MODERATE: { color: '#b87808', fill: '#fff0c2', label: 'Moderate' },
  HIGH: { color: '#e16713', fill: '#ffe3cf', label: 'High' },
  SEVERE: { color: '#c7353f', fill: '#ffe0e2', label: 'Severe' },
}

// Historical-event markers remain an explicitly separate demonstration layer.
// Road and settlement exposure no longer comes from this module.
export const historicalLandslides = [
  { event_id: 'HL-01', latitude: 27.294, longitude: 88.584, event_year: 2018, source_status: 'Demo location' },
  { event_id: 'HL-02', latitude: 27.519, longitude: 88.499, event_year: 2020, source_status: 'Demo location' },
  { event_id: 'HL-03', latitude: 27.154, longitude: 88.349, event_year: 2022, source_status: 'Demo location' },
  { event_id: 'HL-04', latitude: 27.414, longitude: 88.594, event_year: 2019, source_status: 'Demo location' },
]

// Intentionally null until an authoritative Sikkim administrative boundary
// GeoJSON is supplied by the GIS/API integration. Do not substitute mock geometry.
export const sikkimBoundary = null
