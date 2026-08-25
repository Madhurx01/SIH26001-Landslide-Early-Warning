// Permanent Google Cloud Firebase Realtime Database Sync Service
// 24/7/365 Real-Time Cross-Device Synchronization for Vercel, Mobile, and Desktop Command

export const FIREBASE_DB_URL = 'https://sih-26001-default-rtdb.firebaseio.com/reports.json'

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
    // 1. Primary: Google Firebase Realtime Database (Instant Global Cloud Sync)
    try {
      const res = await fetch(FIREBASE_DB_URL, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(data))
          return data
        } else if (data && typeof data === 'object') {
          const list = Object.values(data)
          if (list.length > 0) {
            localStorage.setItem('sih_citizen_reports', JSON.stringify(list))
            return list
          }
        }
      }
    } catch (e) {
      console.warn('Firebase RTDB fetch failed, checking local store', e)
    }

    // 2. Secondary: Local /api/reports fallback
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

    // 1. Direct Cloud PUT to Firebase Realtime Database
    try {
      await fetch(FIREBASE_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
    } catch (e) {
      console.warn('Firebase PUT failed, saving locally', e)
    }

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return fullReport
  },

  updateStatus: async (id, status) => {
    const current = await reportService.getReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))

    // 1. Update Cloud Firebase Realtime Database
    try {
      await fetch(FIREBASE_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
    } catch (e) {
      console.warn('Firebase status update failed', e)
    }

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return updated
  }
}

export default reportService
