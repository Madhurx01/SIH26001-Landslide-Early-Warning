// Authentication & Role-Based Access Control (RBAC) Service
// Implements JWT Token Handling & Role Permissions (Admin / Analyst / Viewer)

export const PRESET_USERS = {
  admin: {
    id: 'USR-001',
    name: 'Col. D. S. Rawat',
    title: 'State Disaster Management Authority (SDMA Lead)',
    email: 'admin@sikkim-sdma.gov.in',
    role: 'admin',
    roleLabel: 'DISASTER COMMANDER (ADMIN)',
    badgeColor: '#c7353f',
    permissions: [
      'VIEW_MAP',
      'TRIGGER_SIRENS',
      'DISPATCH_SDRF',
      'CLOSE_HIGHWAYS',
      'VERIFY_CITIZEN_REPORTS',
      'SYSTEM_CONFIG'
    ],
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJVU1ItMDAxIiwicm9sZSI6ImFkbWluIiwiaXNzIjoiU0lIMjYwMDEifQ.sig_admin_secure_jwt_token_991'
  },
  analyst: {
    id: 'USR-002',
    name: 'Dr. P. Roy',
    title: 'Senior GIS & Landslide Research Scientist',
    email: 'analyst@gsi-nr.res.in',
    role: 'analyst',
    roleLabel: 'GIS SCIENTIST (ANALYST)',
    badgeColor: '#138b9c',
    permissions: [
      'VIEW_MAP',
      'INSPECT_SHAP_MODELS',
      'MONSOON_TIMELINE_SCRUB',
      'SATELLITE_TELEMETRY_ANALYTICS',
      'EXPORT_REPORTS'
    ],
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJVU1ItMDAyIiwicm9sZSI6ImFuYWx5c3QiLCJpc3MiOiJTSUgyNjAwMSJ9.sig_analyst_secure_jwt_token_482'
  },
  viewer: {
    id: 'USR-003',
    name: 'Tenzing Lepcha',
    title: 'Sikkim Resident / Traveler',
    email: 'citizen@sikkim.in',
    role: 'viewer',
    roleLabel: 'CITIZEN (PUBLIC VIEWER)',
    badgeColor: '#27865f',
    permissions: [
      'VIEW_MAP_PUBLIC',
      'CHECK_ROAD_STATUS',
      'SUBMIT_CITIZEN_REPORT',
      'RECEIVE_PUBLIC_ALERTS'
    ],
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJVU1ItMDAzIiwicm9sZSI6InZpZXdlciIsImlzcyI6IlNJSDI2MDAxIn0.sig_viewer_secure_jwt_token_115'
  }
}

export const authService = {
  getCurrentUser: () => {
    try {
      const saved = localStorage.getItem('sih_auth_user')
      if (saved) return JSON.parse(saved)
    } catch (e) {
      console.warn('Could not read auth from localStorage', e)
    }
    return PRESET_USERS.viewer // Default to Citizen (Public Viewer) for all new visitors and unauthenticated sessions
  },

  login: (roleKey = 'admin') => {
    const user = PRESET_USERS[roleKey] || PRESET_USERS.admin
    try {
      localStorage.setItem('sih_auth_user', JSON.stringify(user))
      localStorage.setItem('sih_jwt_token', user.token)
    } catch (e) {
      console.warn('Could not save auth', e)
    }
    return user
  },

  logout: () => {
    try {
      localStorage.removeItem('sih_auth_user')
      localStorage.removeItem('sih_jwt_token')
    } catch (e) {}
    return PRESET_USERS.viewer
  },

  hasPermission: (user, permissionKey) => {
    if (!user || !user.permissions) return false
    return user.permissions.includes(permissionKey)
  }
}

export default authService
