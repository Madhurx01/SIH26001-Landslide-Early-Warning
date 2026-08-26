// Vercel Serverless Function for SMS India Hub Official REST API (cloud.smsindiahub.in)
const http = require('http');
const https = require('https');
const querystring = require('querystring');

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
  const { message = '[NDMA SIKKIM ALERT] Landslide hazard warning active.', numbers, user, password, senderId = 'WEBSMS', channel = 'Trans', isFlash = true } = body;

  if (!user || !password) {
    return res.status(400).json({ error: 'Username and Password are required' });
  }

  const cleanNumbers = (numbers || '')
    .split(/[\n,;]+/)
    .map(n => n.trim().replace(/\D/g, ''))
    .filter(n => n.length >= 10)
    .map(n => (n.length === 10 ? `91${n}` : n))
    .join(',');

  if (!cleanNumbers) {
    return res.status(400).json({ error: 'No valid mobile numbers provided' });
  }

  const queryParams = querystring.stringify({
    user: user.trim(),
    password: password.trim(),
    senderid: senderId.trim(),
    channel: channel.trim(),
    DCS: isFlash ? '8' : '0',
    flashsms: isFlash ? '1' : '0',
    number: cleanNumbers,
    text: message.slice(0, 160),
    route: '1'
  });

  const urlPath = `/api/mt/SendSMS?${queryParams}`;

  const options = {
    hostname: 'cloud.smsindiahub.in',
    path: urlPath,
    method: 'GET'
  };

  return new Promise((resolve) => {
    const request = http.request(options, (response) => {
      let data = '';
      response.on('data', chunk => data += chunk);
      response.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(res.status(200).json(parsed));
        } catch (e) {
          if (data.includes('ErrorCode:000') || data.includes('Done') || data.includes('"ErrorCode":"000"')) {
            resolve(res.status(200).json({ success: true, ErrorCode: '000', ErrorMessage: 'Done', raw: data }));
          } else {
            resolve(res.status(200).json({ success: false, raw: data }));
          }
        }
      });
    });

    request.on('error', (err) => {
      resolve(res.status(500).json({ success: false, error: err.message }));
    });

    request.end();
  });
}
