// Vercel Serverless Function Proxy to Firebase Realtime Database
const https = require('https');

const FIREBASE_DB_URL = 'https://sih-26001-default-rtdb.firebaseio.com/reports.json';

function fetchFirebase() {
  return new Promise((resolve) => {
    https.get(FIREBASE_DB_URL, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (Array.isArray(parsed) && parsed.length > 0) return resolve(parsed);
          if (parsed && typeof parsed === 'object') return resolve(Object.values(parsed));
        } catch (e) {}
        resolve([]);
      });
    }).on('error', () => resolve([]));
  });
}

function updateFirebase(reports) {
  return new Promise((resolve) => {
    const url = new URL(FIREBASE_DB_URL);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' }
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
    const reports = await fetchFirebase();
    return res.status(200).json(reports);
  }

  if (req.method === 'POST') {
    const newReport = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const current = await fetchFirebase();
    const reportId = `CR-${100 + current.length + 1}`;
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
      ...newReport
    };
    const updated = [fullReport, ...current];
    await updateFirebase(updated);
    return res.status(200).json({ success: true, report: fullReport, all: updated });
  }

  if (req.method === 'PATCH') {
    const { id, status } = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const current = await fetchFirebase();
    const updated = current.map(r => r.id === id ? { ...r, status } : r);
    await updateFirebase(updated);
    return res.status(200).json({ success: true, reports: updated });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
