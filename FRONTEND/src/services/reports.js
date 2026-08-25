// Centralized Persistent Report Store for Crowd-Sourced Citizen Observations
// Persists to localStorage with photo previews, GPS coordinates, and status tracking

const DEFAULT_REPORTS = [
  {
    id: 'CR-104',
    location: 'NH-10 (Km 18.2, 20th Mile bend near Singtam)',
    timestamp: '18 mins ago',
    reportedBy: 'Tenzing L. (Local Driver)',
    description: 'Active debris fall and rock tumbling observed across southbound lane. Soil slumping from upper toe cutting.',
    roadBlocked: 'Partial (Single Lane Blocked)',
    status: 'PENDING_VERIFICATION',
    severity: 'HIGH',
    coords: '27.2341°N, 88.4982°E',
    photoUrl: null
  },
  {
    id: 'CR-105',
    location: 'North Sikkim Highway (Chungthang Gorge Km 42)',
    timestamp: '42 mins ago',
    reportedBy: 'Pema D. (BRO Road Worker)',
    description: 'Mudflow slurry pooling along culvert. Tension cracks expanding across roadside retaining wall.',
    roadBlocked: 'No (High Risk of Sudden Blockage)',
    status: 'PENDING_VERIFICATION',
    severity: 'SEVERE',
    coords: '27.6042°N, 88.6431°E',
    photoUrl: null
  }
]

export const reportService = {
  getReports: () => {
    try {
      const stored = localStorage.getItem('sih_citizen_reports')
      if (stored) return JSON.parse(stored)
    } catch (e) {
      console.warn('Could not read reports from localStorage', e)
    }
    return DEFAULT_REPORTS
  },

  addReport: (newReport) => {
    const current = reportService.getReports()
    const reportId = `CR-${100 + current.length + 1}`
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked === 'yes' ? 'SEVERE' : 'HIGH',
      ...newReport
    }
    const updated = [fullReport, ...current]
    try {
      localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    } catch (e) {
      console.warn('Could not save report to localStorage', e)
    }
    return fullReport
  },

  updateStatus: (id, status) => {
    const current = reportService.getReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))
    try {
      localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    } catch (e) {
      console.warn('Could not update report status', e)
    }
    return updated
  }
}

export default reportService
