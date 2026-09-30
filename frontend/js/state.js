// Application State Manager
class StateStore {
  constructor() {
    this.state = {
      activeTab: 'command',
      selectedDistrict: '',
      selectedFacilityType: '',
      currentRole: 'NationalAdmin', // NationalAdmin, DistrictAdmin, Pharmacist, EmergencyCoordinator, MLEngineer
      currentUser: 'Dr. Rajesh Sharma (National Admin)',
      selectedFacilityId: 'FAC-001',
      selectedProductId: 'MED-001',
      isOfflineMode: false,
      offlineQueue: JSON.parse(localStorage.getItem('fnhrip_offline_queue') || '[]'),
      nationalMetrics: null,
      activeLayer: 'ALL', // ALL, HOSPITALS, WAREHOUSES, RISK_STOCK, ICU_STRESS
      alertsCount: 0,
      pendingRecsCount: 0
    };
    this.listeners = [];
  }

  get() {
    return this.state;
  }

  set(partialState) {
    this.state = { ...this.state, ...partialState };
    if (partialState.offlineQueue !== undefined) {
      localStorage.setItem('fnhrip_offline_queue', JSON.stringify(this.state.offlineQueue));
    }
    this.notify();
  }

  subscribe(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }

  notify() {
    this.listeners.forEach(cb => {
      try { cb(this.state); } catch (e) { console.error('State subscriber error:', e); }
    });
  }

  addOfflineAction(action) {
    const queue = [...this.state.offlineQueue, {
      ...action,
      action_id: `act_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
      timestamp: new Date().toISOString()
    }];
    this.set({ offlineQueue: queue });
  }

  clearOfflineQueue() {
    this.set({ offlineQueue: [] });
  }
}

window.State = new StateStore();
