// Permanent Google Cloud Firebase Realtime Database Sync Service
// 24/7/365 Real-Time Cross-Device Synchronization with Verbose Telemetry Logging

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
      const startTime = performance.now()
      const res = await fetch(FIREBASE_DB_URL, { cache: 'no-store' })
      const latency = Math.round(performance.now() - startTime)

      if (res.ok) {
        const data = await res.json()
        let cleanList = []
        if (Array.isArray(data) && data.length > 0) {
          cleanList = data
        } else if (data && typeof data === 'object') {
          cleanList = Object.values(data)
        }

        if (cleanList.length > 0) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(cleanList))
          // Detailed sync log
          console.log(
            `%c☁️ [FIREBASE SYNC] Live sync completed in ${latency}ms | Total Cloud Reports: ${cleanList.length}`,
            'color: #26d0ce; font-size: 11px; font-family: monospace;'
          )
          return cleanList
        }
      }
    } catch (e) {
      console.warn('⚠️ [FIREBASE SYNC WARNING] Cloud fetch issue, using local cache:', e)
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
    console.log('%c🚀 [CITIZEN UPLOAD INITIATED]', 'background: #09272d; color: #26d0ce; font-weight: bold; padding: 4px 8px; border-radius: 4px;')
    console.table({
      Location: newReport.location,
      Coordinates: newReport.coords,
      Reporter: newReport.reportedBy,
      Traffic_Impact: newReport.roadBlocked,
      Photo_Attached: newReport.photoUrl ? 'YES (Base64 Canvas Compressed)' : 'NO'
    })

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
      const startTime = performance.now()
      const res = await fetch(FIREBASE_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
      const uploadDuration = Math.round(performance.now() - startTime)

      if (res.ok) {
        console.log(
          `%c✅ [FIREBASE CLOUD SUCCESS] Report ${fullReport.id} published to Google Cloud in ${uploadDuration}ms!`,
          'background: #27865f; color: #fff; font-weight: bold; padding: 4px 8px; border-radius: 4px;'
        )
      } else {
        console.warn('⚠️ [FIREBASE UPLOAD FAILED] Status code:', res.status)
      }
    } catch (e) {
      console.error('❌ [FIREBASE UPLOAD ERROR]:', e)
    }

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return fullReport
  },

  updateStatus: async (id, status) => {
    console.log(`%c🛡️ [ADMIN COMMAND ACTION] Updating ${id} -> ${status}`, 'color: #ff8a93; font-weight: bold;')
    const current = await reportService.getReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))

    try {
      await fetch(FIREBASE_DB_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
      console.log(`%c✅ [STATUS SYNCED] ${id} status updated on Firebase Cloud DB`, 'color: #74e0b1;')
    } catch (e) {
      console.warn('Firebase status update failed:', e)
    }

    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return updated
  }
}

export default reportService
