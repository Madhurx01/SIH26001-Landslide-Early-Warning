import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { exec } from 'child_process'

const DB_PATH = path.resolve(__dirname, 'src/data/pooledReportsDb.json')
const WHITELIST_PATH = path.resolve(__dirname, 'src/data/ipWhitelist.json')
const ADB_SCRIPT = path.resolve(__dirname, 'server/send_sms_adb.py')

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
]

const DEFAULT_WHITELIST = ['47.29.188.162', '127.0.0.1', '::1', 'localhost']

function ensureStorage() {
  if (!fs.existsSync(DB_PATH)) {
    fs.writeFileSync(DB_PATH, JSON.stringify(DEFAULT_REPORTS, null, 2))
  }
  if (!fs.existsSync(WHITELIST_PATH)) {
    fs.writeFileSync(WHITELIST_PATH, JSON.stringify(DEFAULT_WHITELIST, null, 2))
  }
}

// Custom Vite Middleware for ADB USB Bridge, Shared Pooled Reports & IP Detection
function apiMiddlewarePlugin() {
  ensureStorage()
  return {
    name: 'sih-shared-api-middleware',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        res.setHeader('Access-Control-Allow-Origin', '*')
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS')
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')

        if (req.method === 'OPTIONS') {
          res.statusCode = 204
          res.end()
          return
        }

        const url = req.url.split('?')[0]

        // 1. ADB Status Check Endpoint
        if (url === '/api/adbStatus' && req.method === 'GET') {
          exec(`python3 "${ADB_SCRIPT}" status`, (error, stdout) => {
            res.setHeader('Content-Type', 'application/json')
            try {
              res.end(stdout.trim() || JSON.stringify({ connected: false }))
            } catch (e) {
              res.end(JSON.stringify({ connected: false, error: e.message }))
            }
          })
          return
        }

        // 2. ADB SMS Dispatch Endpoint
        if (url === '/api/sendAdbSms' && req.method === 'POST') {
          let body = ''
          req.on('data', chunk => { body += chunk })
          req.on('end', () => {
            try {
              const { numbers = [], message = '' } = JSON.parse(body)
              const results = []
              let count = 0

              if (numbers.length === 0) {
                res.setHeader('Content-Type', 'application/json')
                res.statusCode = 400
                res.end(JSON.stringify({ success: false, error: 'No phone numbers provided' }))
                return
              }

              numbers.forEach((num) => {
                const escapedMsg = message.replace(/"/g, '\\"')
                exec(`python3 "${ADB_SCRIPT}" "${num}" "${escapedMsg}"`, (error, stdout) => {
                  try {
                    results.push(JSON.parse(stdout.trim()))
                  } catch (e) {
                    results.push({ number: num, success: false, error: stdout })
                  }
                  count++
                  if (count === numbers.length) {
                    res.setHeader('Content-Type', 'application/json')
                    const anySuccess = results.some(r => r.success)
                    res.statusCode = anySuccess ? 200 : 400
                    res.end(JSON.stringify({ success: anySuccess, results }))
                  }
                })
              })
            } catch (e) {
              res.setHeader('Content-Type', 'application/json')
              res.statusCode = 400
              res.end(JSON.stringify({ success: false, error: e.message }))
            }
          })
          return
        }

        // 3. IP Detection Endpoint
        if (url === '/api/ip' && req.method === 'GET') {
          const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress || '127.0.0.1'
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ ip: clientIp }))
          return
        }

        // 4. IP Whitelist Management
        if (url === '/api/whitelist') {
          if (req.method === 'GET') {
            ensureStorage()
            const data = fs.readFileSync(WHITELIST_PATH, 'utf-8')
            res.setHeader('Content-Type', 'application/json')
            res.end(data)
            return
          } else if (req.method === 'POST') {
            let body = ''
            req.on('data', chunk => { body += chunk })
            req.on('end', () => {
              try {
                const { ip } = JSON.parse(body)
                ensureStorage()
                const current = JSON.parse(fs.readFileSync(WHITELIST_PATH, 'utf-8'))
                if (ip && !current.includes(ip)) {
                  current.push(ip)
                  fs.writeFileSync(WHITELIST_PATH, JSON.stringify(current, null, 2))
                }
                res.setHeader('Content-Type', 'application/json')
                res.end(JSON.stringify({ success: true, whitelist: current }))
              } catch (e) {
                res.statusCode = 400
                res.end(JSON.stringify({ error: 'Invalid payload' }))
              }
            })
            return
          }
        }

        // 5. Shared Pooled Reports Store
        if (url === '/api/reports') {
          if (req.method === 'GET') {
            ensureStorage()
            const data = fs.readFileSync(DB_PATH, 'utf-8')
            res.setHeader('Content-Type', 'application/json')
            res.end(data)
            return
          } else if (req.method === 'POST') {
            let body = ''
            req.on('data', chunk => { body += chunk })
            req.on('end', () => {
              try {
                const newReport = JSON.parse(body)
                ensureStorage()
                const current = JSON.parse(fs.readFileSync(DB_PATH, 'utf-8'))
                const reportId = `CR-${100 + current.length + 1}`
                const fullReport = {
                  id: reportId,
                  timestamp: 'Just now',
                  status: 'PENDING_VERIFICATION',
                  severity: newReport.roadBlocked?.includes('Full') ? 'SEVERE' : 'HIGH',
                  ...newReport
                }
                const updated = [fullReport, ...current]
                fs.writeFileSync(DB_PATH, JSON.stringify(updated, null, 2))
                res.setHeader('Content-Type', 'application/json')
                res.end(JSON.stringify({ success: true, report: fullReport, all: updated }))
              } catch (e) {
                console.error('Error saving pooled report:', e)
                res.statusCode = 400
                res.end(JSON.stringify({ error: 'Invalid report payload' }))
              }
            })
            return
          } else if (req.method === 'PATCH' || req.method === 'PUT') {
            let body = ''
            req.on('data', chunk => { body += chunk })
            req.on('end', () => {
              try {
                const { id, status } = JSON.parse(body)
                ensureStorage()
                const current = JSON.parse(fs.readFileSync(DB_PATH, 'utf-8'))
                const updated = current.map(r => r.id === id ? { ...r, status } : r)
                fs.writeFileSync(DB_PATH, JSON.stringify(updated, null, 2))
                res.setHeader('Content-Type', 'application/json')
                res.end(JSON.stringify({ success: true, reports: updated }))
              } catch (e) {
                res.statusCode = 400
                res.end(JSON.stringify({ error: 'Invalid update payload' }))
              }
            })
            return
          }
        }

        next()
      })
    }
  }
}

export default defineConfig({
  plugins: [react(), apiMiddlewarePlugin()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    cors: true,
    allowedHosts: true
  }
})
