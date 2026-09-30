// FNHRIP API Client with Sovereign JWT Authentication
const API_BASE = '/api/v1';

const Api = {
  getToken() {
    return localStorage.getItem('fnhrip_jwt_token');
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('fnhrip_jwt_token', token);
    } else {
      localStorage.removeItem('fnhrip_jwt_token');
    }
  },

  async ensureAuth() {
    let token = this.getToken();
    if (!token) {
      if (!window.location.pathname.endsWith('login.html') && !window.location.pathname.endsWith('/login')) {
        window.location.href = '/login.html';
        return null;
      }
    }
    return token;
  },

  logout() {
    this.setToken(null);
    localStorage.removeItem('fnhrip_user_profile');
    window.location.href = '/login.html';
  },

  async switchRole(role) {
    try {
      const res = await fetch(`${API_BASE}/auth/switch-role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        this.setToken(data.token);
        if (window.State && data.user) {
          window.State.set({
            currentRole: data.user.role,
            currentUser: data.user.name,
            userTitle: data.user.title,
            userBadge: data.user.badge,
            userPermissions: data.user.permissions
          });
        }
        return data;
      }
      throw new Error(data.error || `Failed to switch role to ${role}`);
    } catch (err) {
      console.error('switchRole error:', err);
      throw err;
    }
  },

  async getHeaders(customHeaders = {}) {
    const headers = { 'Accept': 'application/json', ...customHeaders };
    const token = await this.ensureAuth();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  },

  async get(endpoint, params = {}) {
    try {
      const url = new URL(endpoint.startsWith('http') ? endpoint : `${window.location.origin}${API_BASE}${endpoint}`);
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
          url.searchParams.append(key, params[key]);
        }
      });
      const headers = await this.getHeaders();
      const res = await fetch(url.toString(), { headers });
      if (!res.ok) {
        let errData = {};
        try { errData = await res.json(); } catch (_) {}
        throw new Error(errData.error || `HTTP ${res.status}: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`API GET error on ${endpoint}:`, err);
      throw err;
    }
  },

  async post(endpoint, body = {}) {
    try {
      const headers = await this.getHeaders({ 'Content-Type': 'application/json' });
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      console.error(`API POST error on ${endpoint}:`, err);
      throw err;
    }
  },

  async patch(endpoint, body = {}) {
    try {
      const headers = await this.getHeaders({ 'Content-Type': 'application/json' });
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      console.error(`API PATCH error on ${endpoint}:`, err);
      throw err;
    }
  },

  // Auth service
  login: (username, password) => Api.post('/auth/login', { username, password }),
  getProfile: () => Api.get('/auth/me'),
  getRoles: () => Api.get('/auth/roles'),

  // Specific service calls
  getNationalMetrics: () => Api.get('/national-metrics'),
  getHierarchy: () => Api.get('/hierarchy'),
  getFacilities: (params) => Api.get('/facilities', params),
  getFacilityDetail: (id) => Api.get(`/facilities/${id}`),
  getProducts: () => Api.get('/products'),
  getInventory: (params) => Api.get('/inventory', params),
  getFacilityBatches: (id) => Api.get(`/inventory/facility/${id}/batches`),
  getFefoExpiries: (days = 45) => Api.get('/inventory/fefo-expiries', { days_threshold: days }),
  postTransaction: (data) => Api.post('/inventory/transactions', data),
  getBeds: (params) => Api.get('/beds', params),
  getWorkforce: (params) => Api.get('/workforce', params),
  getAlerts: (params) => Api.get('/alerts', params),
  updateAlertStatus: (id, status, owner) => Api.patch(`/alerts/${id}/status`, { status, owner }),
  getForecast: (fid, pid, horizon = 30) => Api.get('/forecasts/demand', { facility_id: fid, product_id: pid, horizon_days: horizon }),
  getStockoutPredictions: (params) => Api.get('/predictions/stockouts', params),
  getAnomalies: () => Api.get('/anomalies'),
  getRecommendations: (status) => Api.get('/recommendations', { status }),
  approveRecommendation: (id, notes, approvedBy) => Api.post(`/recommendations/${id}/approve`, { notes, approved_by: approvedBy }),
  rejectRecommendation: (id, notes, rejectedBy) => Api.post(`/recommendations/${id}/reject`, { notes, rejected_by: rejectedBy }),
  runSimulation: (params) => Api.post('/simulation/run', params),
  getFederatedOverview: () => Api.get('/federated/overview'),
  runFederatedRound: (modelId) => Api.post('/federated/run-round', { model_id: modelId }),
  syncOfflineBatch: (fid, actions) => Api.post('/sync/batch', { facility_id: fid, queued_actions: actions }),
  getAuditLogs: (limit = 50, page = 1) => Api.get('/audit/logs', { limit, page }),
  verifyAuditChain: () => Api.get('/audit/verify')
};

window.Api = Api;
