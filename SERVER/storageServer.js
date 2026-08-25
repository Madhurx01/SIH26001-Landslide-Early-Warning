// Dedicated Live Shared Pool Storage Server for Sikkim Landslide Early Warning System
// Runs standalone on port 4000 with 100% CORS support for Vercel & Mobile Devices

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 4000;
const DB_FILE = path.join(__dirname, 'reports_db.json');

const INITIAL_REPORTS = [
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
];

function loadReports() {
  try {
    if (fs.existsSync(DB_FILE)) {
      return JSON.parse(fs.readFileSync(DB_FILE, 'utf-8'));
    }
  } catch (e) {
    console.error('Error reading DB:', e);
  }
  fs.writeFileSync(DB_FILE, JSON.stringify(INITIAL_REPORTS, null, 2));
  return INITIAL_REPORTS;
}

function saveReports(reports) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(reports, null, 2));
  } catch (e) {
    console.error('Error writing DB:', e);
  }
}

const server = http.createServer((req, res) => {
  // Global CORS Headers for all devices & Vercel
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');

  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    res.end();
    return;
  }

  const url = req.url.split('?')[0];

  // Health Check
  if (url === '/' || url === '/health') {
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({
      status: 'ONLINE',
      service: 'Sikkim LEWS Shared Pooled Storage Server',
      total_reports: loadReports().length,
      timestamp: new Date().toISOString()
    }));
    return;
  }

  // 1. GET /api/reports
  if (url === '/api/reports' && req.method === 'GET') {
    const reports = loadReports();
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(reports));
    return;
  }

  // 2. POST /api/reports
  if (url === '/api/reports' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const newReport = JSON.parse(body);
        const current = loadReports();
        const reportId = `CR-${100 + current.length + 1}`;
        const fullReport = {
          id: reportId,
          timestamp: 'Just now',
          status: 'PENDING_VERIFICATION',
          severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
          ...newReport
        };
        const updated = [fullReport, ...current];
        saveReports(updated);
        console.log(`🚨 [NEW CITIZEN REPORT] ID: ${fullReport.id} | Location: ${fullReport.location} | Reporter: ${fullReport.reportedBy}`);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ success: true, report: fullReport, all: updated }));
      } catch (err) {
        console.error('POST error:', err);
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Invalid JSON payload' }));
      }
    });
    return;
  }

  // 3. PATCH /api/reports
  if (url === '/api/reports' && (req.method === 'PATCH' || req.method === 'PUT')) {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { id, status } = JSON.parse(body);
        const current = loadReports();
        const updated = current.map(r => r.id === id ? { ...r, status } : r);
        saveReports(updated);
        console.log(`✅ [ADMIN STATUS UPDATE] ID: ${id} -> ${status}`);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ success: true, reports: updated }));
      } catch (err) {
        res.statusCode = 400;
        res.end(JSON.stringify({ error: 'Invalid JSON payload' }));
      }
    });
    return;
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ error: 'Not Found' }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`🏔️ Sikkim Shared Pool Storage Server running on http://0.0.0.0:${PORT}`);
});
