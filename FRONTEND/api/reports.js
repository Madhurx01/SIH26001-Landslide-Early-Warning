// Vercel Serverless Global Cloud Database Bridge
// Syncs across Vercel deployments, mobile devices, and admin laptops with 0 CORS issues

const https = require('https');

const CLOUD_DB_URL = 'https://extendsclass.com/api/json-storage/bin/caaeadf';

const DEFAULT_REPORTS = [
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

function fetchCloud() {
  return new Promise((resolve) => {
    https.get(CLOUD_DB_URL, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (Array.isArray(parsed) && parsed.length > 0) return resolve(parsed);
        } catch (e) {}
        resolve(DEFAULT_REPORTS);
      });
    }).on('error', () => resolve(DEFAULT_REPORTS));
  });
}

function updateCloud(reports) {
  return new Promise((resolve) => {
    const url = new URL(CLOUD_DB_URL);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      }
    }, (res) => {
      res.on('data', () => {});
      res.on('end', () => resolve(true));
    });
    req.on('error', () => resolve(false));
    req.write(JSON.stringify(reports));
    req.end();
  });
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  if (req.method === 'GET') {
    const reports = await fetchCloud();
    return res.status(200).json(reports);
  }

  if (req.method === 'POST') {
    const newReport = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const current = await fetchCloud();
    const reportId = `CR-${100 + current.length + 1}`;
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
      ...newReport
    };
    const updated = [fullReport, ...current];
    await updateCloud(updated);
    return res.status(200).json({ success: true, report: fullReport, all: updated });
  }

  if (req.method === 'PATCH') {
    const { id, status } = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const current = await fetchCloud();
    const updated = current.map(r => r.id === id ? { ...r, status } : r);
    await updateCloud(updated);
    return res.status(200).json({ success: true, reports: updated });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
