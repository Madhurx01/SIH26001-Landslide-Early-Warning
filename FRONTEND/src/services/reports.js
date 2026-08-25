// Global Cloud-Synchronized Storage Service for Citizen Incident Reports
// Real-time synchronization across Vercel deployments, mobile devices, and admin laptops

const CLOUD_DB_URL = 'https://extendsclass.com/api/json-storage/bin/caaeadf'

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
    // 1. Fetch from Global Cloud Database (Vercel & multi-device sync)
    try {
      const res = await fetch(CLOUD_DB_URL, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(data))
          return data
        }
      }
    } catch (e) {
      console.warn('Cloud DB fetch failed, checking local API/cache', e)
    }

    // 2. Fallback to local Vite API if running locally
    try {
      const localRes = await fetch('/api/reports')
      if (localRes.ok) {
        const localData = await localRes.json()
        if (Array.isArray(localData)) return localData
      }
    } catch (err) {}

    return reportService.getInitialReports()
  },

  addReport: async (newReport) => {
    const current = await reportService.getReports()
    const reportId = `CR-${100 + current.length + 1}`
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
      ...newReport
    }
    const updated = [fullReport, ...current]

    // 1. Push to Global Cloud Database so everyone sees it instantly
    try {
      await fetch(CLOUD_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
    } catch (e) {
      console.warn('Cloud DB PUT failed, saving to local store', e)
    }

    // 2. Local fallback
    try {
      fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newReport)
      }).catch(() => {})
    } catch (err) {}

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return fullReport
  },

  updateStatus: async (id, status) => {
    const current = await reportService.getReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))

    // 1. Update Global Cloud Database
    try {
      await fetch(CLOUD_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
    } catch (e) {
      console.warn('Cloud DB update failed', e)
    }

    // 2. Local API fallback
    try {
      fetch('/api/reports', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status })
      }).catch(() => {})
    } catch (err) {}

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return updated
  }
}

export default reportService
