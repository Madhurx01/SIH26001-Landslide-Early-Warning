// IP Access Control & Whitelist Guard Service
// Enforces IP-Gated Access for Disaster Commander (Admin) Role

export const MASTER_ADMIN_IP = '47.29.188.162'
export const MASTER_OVERRIDE_PASSCODE = 'SIH2026-SDMA-MASTER'

const DEFAULT_WHITELIST = [
  '47.29.188.162',
  '127.0.0.1',
  '::1',
  'localhost',
  '10.233.213.24',
  '10.233.213.63'
]

export const ipGuard = {
  detectClientIp: async () => {
    try {
      const res = await fetch('https://api.ipify.org?format=json', { timeout: 3000 })
      if (res.ok) {
        const data = await res.json()
        return data.ip
      }
    } catch (e) {
      try {
        const res2 = await fetch('/api/ip')
        if (res2.ok) {
          const data2 = await res2.json()
          return data2.ip
        }
      } catch (err) {}
    }
    return MASTER_ADMIN_IP // Default to master admin IP if offline
  },

  getWhitelistedIps: () => {
    try {
      const saved = localStorage.getItem('sih_whitelisted_ips')
      if (saved) return JSON.parse(saved)
    } catch (e) {}
    return DEFAULT_WHITELIST
  },

  isIpWhitelisted: (ip) => {
    if (!ip) return true
    const list = ipGuard.getWhitelistedIps()
    if (ip === MASTER_ADMIN_IP || ip.startsWith('127.') || ip.startsWith('10.') || ip.startsWith('192.168.')) {
      return true
    }
    return list.includes(ip)
  },

  approveIp: (newIp) => {
    const list = ipGuard.getWhitelistedIps()
    if (newIp && !list.includes(newIp)) {
      const updated = [...list, newIp.trim()]
      localStorage.setItem('sih_whitelisted_ips', JSON.stringify(updated))
      try {
        fetch('/api/whitelist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ip: newIp })
        })
      } catch (e) {}
      return updated
    }
    return list
  },

  removeIp: (ipToRemove) => {
    if (ipToRemove === MASTER_ADMIN_IP) return ipGuard.getWhitelistedIps() // Cannot remove master
    const list = ipGuard.getWhitelistedIps().filter(ip => ip !== ipToRemove)
    localStorage.setItem('sih_whitelisted_ips', JSON.stringify(list))
    return list
  },

  validateMasterPasscode: (passcode, currentIp) => {
    if (passcode.trim() === MASTER_OVERRIDE_PASSCODE) {
      if (currentIp) ipGuard.approveIp(currentIp)
      return true
    }
    return false
  }
}

export default ipGuard
