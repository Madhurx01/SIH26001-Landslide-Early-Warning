// Dedicated Live Shared Pool Storage Service
// Direct connection to Dedicated Storage Server (https://d46babf2acd1b6.lhr.life)

export const STORAGE_SERVER_URL = 'https://57de918ddfd350.lhr.life/api/reports'

export const DEFAULT_REPORTS = [
  {
    id: 'CR-104',
    location: 'NH-10 (Km 18.2, 20th Mile bend near Singtam)',
    timestamp: '18 mins ago',
    reportedBy: 'Tenzing L. (Local Driver)',
    description: 'Active debris fall and rock tumbling observed across southbound lane. Soil slumping from upper toe cutting.',
    roadBlocked: 'Partial (Single Lane)',
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
    roadBlocked: 'No Blockage',
    status: 'PENDING_VERIFICATION',
    severity: 'SEVERE',
    coords: '27.6042°N, 88.6431°E',
    photoUrl: null
  }
]

export const reportService = {
  getInitialReports: () => {
    try {
      const stored = localStorage.getItem('sih_citizen_reports')
      if (stored) {
        const parsed = JSON.parse(stored)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch (e) {}
    return DEFAULT_REPORTS
  },

  getReports: async () => {
    // 1. Primary: Dedicated Live Storage Server
    try {
      const res = await fetch(STORAGE_SERVER_URL, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(data))
          return data
        }
      }
    } catch (e) {
      console.warn('Dedicated storage server unavailable, checking local endpoint', e)
    }

    // 2. Secondary: Local /api/reports endpoint
    try {
      const res2 = await fetch('/api/reports', { cache: 'no-store' })
      if (res2.ok) {
        const data2 = await res2.json()
        if (Array.isArray(data2) && data2.length > 0) return data2
      }
    } catch (err) {}

    return reportService.getInitialReports()
  },

  addReport: async (newReport) => {
    // 1. Primary: POST to Dedicated Live Storage Server
    try {
      const res = await fetch(STORAGE_SERVER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newReport)
      })
      if (res.ok) {
        const data = await res.json()
        if (data.report) {
          if (data.all) localStorage.setItem('sih_citizen_reports', JSON.stringify(data.all))
          return data.report
        }
      }
    } catch (e) {
      console.warn('Dedicated storage POST failed, attempting local fallback', e)
    }

    // 2. Secondary fallback
    try {
      const res2 = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newReport)
      })
      if (res2.ok) {
        const data2 = await res2.json()
        if (data2.report) return data2.report
      }
    } catch (err) {}

    // 3. Local storage fallback
    const current = reportService.getInitialReports()
    const reportId = `CR-${100 + current.length + 1}`
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
      ...newReport
    }
    const updated = [fullReport, ...current]
    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return fullReport
  },

  updateStatus: async (id, status) => {
    // 1. Primary: PATCH to Dedicated Live Storage Server
    try {
      const res = await fetch(STORAGE_SERVER_URL, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status })
      })
      if (res.ok) {
        const data = await res.json()
        if (data.reports) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(data.reports))
          return data.reports
        }
      }
    } catch (e) {
      console.warn('Dedicated storage PATCH failed', e)
    }

    const current = reportService.getInitialReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))
    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return updated
  }
}

export default reportService
