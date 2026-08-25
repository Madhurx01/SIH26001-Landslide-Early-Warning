// Vercel Serverless Function for Pooled Citizen Reports
let memoryReports = [
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

export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  if (req.method === 'GET') {
    return res.status(200).json(memoryReports);
  }

  if (req.method === 'POST') {
    const newReport = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const reportId = `CR-${100 + memoryReports.length + 1}`;
    const fullReport = {
      id: reportId,
      timestamp: 'Just now',
      status: 'PENDING_VERIFICATION',
      severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
      ...newReport
    };
    memoryReports = [fullReport, ...memoryReports];
    return res.status(200).json({ success: true, report: fullReport, all: memoryReports });
  }

  if (req.method === 'PATCH') {
    const { id, status } = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    memoryReports = memoryReports.map(r => r.id === id ? { ...r, status } : r);
    return res.status(200).json({ success: true, reports: memoryReports });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
