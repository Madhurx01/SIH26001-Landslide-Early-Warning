// Universal Pooled Incident Reports Service
// Communicates with /api/reports for seamless Vercel cloud and local dev syncing

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
    try {
      const res = await fetch('/api/reports', { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          localStorage.setItem('sih_citizen_reports', JSON.stringify(data))
          return data
        }
      }
    } catch (e) {
      console.warn('Failed to fetch /api/reports, using local cache', e)
    }

    return reportService.getInitialReports()
  },

  addReport: async (newReport) => {
    try {
      const res = await fetch('/api/reports', {
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
      console.warn('POST /api/reports failed, saving locally', e)
    }

    // Local fallback
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
    try {
      const res = await fetch('/api/reports', {
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
      console.warn('PATCH /api/reports failed, saving locally', e)
    }

    const current = reportService.getInitialReports()
    const updated = current.map((r) => (r.id === id ? { ...r, status } : r))
    localStorage.setItem('sih_citizen_reports', JSON.stringify(updated))
    return updated
  }
}

export default reportService
