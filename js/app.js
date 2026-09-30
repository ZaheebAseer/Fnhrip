// Master Application Controller
const App = {
  async init() {
    console.log('Initializing FNHRIP Sovereign Platform Client...');
    
    // Bind Navigation & Global Listeners
    this.bindNavigation();
    this.bindFilters();
    this.bindModals();
    this.bindRoleSwitcher();

    // Initialize Map
    window.mapInstance = new NationalMap('nationalMapCanvas');

    // Initialize sub-modules
    window.Simulator.init();
    window.Federated.init();
    window.OfflineApp.init();

    // Ensure sovereign authentication session. If not logged in, redirect to login page
    const token = await window.Api.ensureAuth();
    if (!token) {
      return; // redirecting to login.html
    }

    // Restore cached user profile if present
    try {
      const savedProfile = JSON.parse(localStorage.getItem('fnhrip_user_profile') || 'null');
      if (savedProfile) {
        window.State.set({
          currentRole: savedProfile.role,
          currentUser: savedProfile.name,
          userTitle: savedProfile.title,
          userBadge: savedProfile.badge,
          userPermissions: savedProfile.permissions
        });
      }
    } catch (_) {}

    const activeRole = window.State.get().currentRole || 'ADMIN';
    this.applyRolePermissions(activeRole);

    // Initial Data Fetch
    await this.refreshAllData();

    // Setup periodic polling for live updates every 30s
    setInterval(() => {
      if (!window.State.get().isOfflineMode) {
        this.fetchMetrics();
      }
    }, 30000);
  },

  bindNavigation() {
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.getAttribute('data-tab');
        if (tab) {
          this.switchTab(tab);
        }
      });
    });

    // Map layer toolbar
    const layerBtns = document.querySelectorAll('.map-layer-btn');
    layerBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        layerBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const layer = btn.getAttribute('data-layer');
        if (window.mapInstance) {
          window.mapInstance.setLayer(layer);
        }
      });
    });
  },

  switchTab(tabName) {
    window.State.set({ activeTab: tabName });

    // Update nav links
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
      if (item.getAttribute('data-tab') === tabName) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Update views
    document.querySelectorAll('.view-content').forEach(view => {
      if (view.id === `view-${tabName}`) {
        view.classList.add('active');
      } else {
        view.classList.remove('active');
      }
    });

    // Update header title
    const titles = {
      'command': 'Command Centre',
      'weather': 'Supply Weather Forecast',
      'cascade': 'Cascade Failure Simulator',
      'ledger': 'Impact Ledger',
      'national-map': 'National Command Centre & GIS Intelligence',
      'inventory': 'Medicine Supply-Chain & FEFO Intelligence',
      'capacity': 'Healthcare Bed Capacity & Staffing Hub',
      'predictions': 'Predictive AI & Early Warning Engine',
      'recommendations': 'AI Decision Support & Human Approvals',
      'simulator': 'What-If Emergency Scenario Simulator',
      'federated': 'Federated Learning Network & Coordinator',
      'offline': 'Offline-First PHC Field Station',
      'audit': 'Tamper-Evident Sovereign Audit Ledger'
    };
    const titleEl = document.getElementById('viewTitleHeading');
    if (titleEl && titles[tabName]) {
      titleEl.innerText = titles[tabName];
    }

    // Refresh specific view data if needed
    if (window.TabHooks && window.TabHooks[tabName]) window.TabHooks[tabName]();
    if (tabName === 'command' && window.loadCommandCentre) window.loadCommandCentre();
    if (tabName === 'inventory') this.loadInventoryView();
    if (tabName === 'capacity') this.loadCapacityView();
    if (tabName === 'predictions') this.loadPredictionsView();
    if (tabName === 'recommendations') this.loadRecommendationsView();
    if (tabName === 'audit') this.loadAuditView();
    if (tabName === 'national-map' && window.mapInstance) {
      setTimeout(() => window.mapInstance.draw(), 50);
    }
  },

  bindFilters() {
    const districtSelect = document.getElementById('filterDistrictSelect');
    if (districtSelect) {
      districtSelect.addEventListener('change', (e) => {
        window.State.set({ selectedDistrict: e.target.value });
        this.refreshAllData();
      });
    }

    const typeSelect = document.getElementById('filterFacilityTypeSelect');
    if (typeSelect) {
      typeSelect.addEventListener('change', (e) => {
        window.State.set({ selectedFacilityType: e.target.value });
        this.refreshAllData();
      });
    }
  },

  bindRoleSwitcher() {
    const roleSelect = document.getElementById('roleSwitcherSelect');
    if (roleSelect) {
      roleSelect.addEventListener('change', async (e) => {
        const role = e.target.value;
        await this.handleRoleSwitch(role);
      });
    }
  },

  async handleRoleSwitch(role) {
    try {
      const res = await window.Api.switchRole(role);
      localStorage.setItem('fnhrip_user_profile', JSON.stringify(res.user));
      this.applyRolePermissions(res.user.role);
      this.showToast(`Active RBAC Role: ${res.user.role} — ${res.user.badge}`, 'success');
      
      // Re-render active views that have role-dependent controls
      const activeTab = window.State.get().activeTab;
      if (activeTab === 'recommendations') {
        this.loadRecommendationsView();
      } else if (activeTab === 'inventory') {
        this.loadInventoryView();
      }
    } catch (err) {
      console.error('Role switch error:', err);
      this.showToast(`Role switch failed: ${err.message}`, 'error');
    }
  },

  handleSignOut() {
    if (confirm('Sign out from sovereign node session and return to credential gateway?')) {
      window.Api.logout();
    }
  },

  applyRolePermissions(role) {
    const canonical = (role || 'ADMIN').toUpperCase();
    const roleConfig = {
      'ADMIN': {
        label: 'ADMIN: Full Access',
        dot: '#0284c7',
        bg: '#e0f2fe',
        border: '#7dd3fc',
        color: '#0369a1',
        canPostTx: true,
        canApproveRecs: true,
        canRunSim: true,
        canRunFed: true
      },
      'HEALTH_OFFICER': {
        label: 'HEALTH OFFICER: Allocations',
        dot: '#d97706',
        bg: '#fffbeb',
        border: '#fde68a',
        color: '#b45309',
        canPostTx: true,
        canApproveRecs: true,
        canRunSim: true,
        canRunFed: false
      },
      'PHC_OPERATOR': {
        label: 'PHARMACIST: Dispensing Only',
        dot: '#0d9488',
        bg: '#ecfdf5',
        border: '#a7f3d0',
        color: '#047857',
        canPostTx: true,
        canApproveRecs: false,
        canRunSim: false,
        canRunFed: false
      },
      'ML_ENGINEER': {
        label: 'ML ENGINEER: AI & FedAvg',
        dot: '#7c3aed',
        bg: '#f5f3ff',
        border: '#ddd6fe',
        color: '#6d28d9',
        canPostTx: false,
        canApproveRecs: false,
        canRunSim: true,
        canRunFed: true
      },
      'VIEWER': {
        label: 'VIEWER: Read-Only Surveillance',
        dot: '#64748b',
        bg: '#f1f5f9',
        border: '#cbd5e1',
        color: '#334155',
        canPostTx: false,
        canApproveRecs: false,
        canRunSim: false,
        canRunFed: false
      }
    };

    const cfg = roleConfig[canonical] || roleConfig['VIEWER'];

    // Update Header Badge
    const badge = document.getElementById('headerRoleBadge');
    const label = document.getElementById('headerRoleLabel');
    const dot = document.getElementById('headerRoleDot');
    if (badge && label && dot) {
      label.innerText = cfg.label;
      dot.style.background = cfg.dot;
      badge.style.background = cfg.bg;
      badge.style.borderColor = cfg.border;
      badge.style.color = cfg.color;
    }

    // Role switcher select value synchronization
    const roleSelect = document.getElementById('roleSwitcherSelect');
    if (roleSelect && roleSelect.value !== canonical) {
      for (let opt of roleSelect.options) {
        if (opt.value === canonical) {
          roleSelect.value = canonical;
          break;
        }
      }
    }

    // Post Transaction Button styling & tooltip
    const btnNewTx = document.getElementById('btnOpenNewTxModal');
    if (btnNewTx) {
      if (!cfg.canPostTx) {
        btnNewTx.style.opacity = '0.5';
        btnNewTx.title = 'Access Restricted: Requires Hospital Pharmacist, Health Officer, or Admin';
      } else {
        btnNewTx.style.opacity = '1';
        btnNewTx.title = 'Post Inventory Transaction';
      }
    }

    // Simulation Button
    const runSimBtn = document.getElementById('btnRunSimulation');
    if (runSimBtn) {
      if (!cfg.canRunSim) {
        runSimBtn.classList.add('btn-disabled');
        runSimBtn.title = 'Access Restricted: Requires ML Engineer, Health Officer, or Admin';
      } else {
        runSimBtn.classList.remove('btn-disabled');
        runSimBtn.title = 'Simulate Emergency Scenario';
      }
    }

    // Federated Round Button
    const runFedBtn = document.getElementById('btnRunFedRound');
    if (runFedBtn) {
      if (!cfg.canRunFed) {
        runFedBtn.classList.add('btn-disabled');
        runFedBtn.title = 'Access Restricted: Requires ML Engineer or Admin';
      } else {
        runFedBtn.classList.remove('btn-disabled');
        runFedBtn.title = 'Trigger Federated Aggregation Round';
      }
    }
  },

  bindModals() {
    // New transaction button & modal
    const btnNewTx = document.getElementById('btnOpenNewTxModal');
    const modalTx = document.getElementById('modalTransaction');
    const btnCloseTx = document.getElementById('btnCloseTxModal');
    const formTx = document.getElementById('formNewTransaction');

    if (btnNewTx && modalTx) {
      btnNewTx.addEventListener('click', () => {
        const role = (window.State.get().currentRole || '').toUpperCase();
        if (!['ADMIN', 'HEALTH_OFFICER', 'PHC_OPERATOR'].includes(role)) {
          this.showToast(`Access Denied (403): Role '${role}' cannot post inventory transactions. Requires Hospital Pharmacist, Health Officer, or Admin.`, 'error');
          return;
        }
        modalTx.classList.add('active');
      });
    }
    if (btnCloseTx && modalTx) {
      btnCloseTx.addEventListener('click', () => { modalTx.classList.remove('active'); });
    }
    if (formTx) {
      formTx.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.handleCreateTransaction();
      });
    }

    // Facility Inspector Drawer close
    const btnCloseDrawer = document.getElementById('btnCloseFacilityDrawer');
    const drawer = document.getElementById('facilityInspectorDrawer');
    if (btnCloseDrawer && drawer) {
      btnCloseDrawer.addEventListener('click', () => { drawer.classList.remove('active'); });
    }
  },

  async refreshAllData() {
    await Promise.all([
      this.fetchMetrics(),
      this.loadFacilities(),
      this.populateFilterDropdowns()
    ]);
  },

  async fetchMetrics() {
    try {
      const data = await window.Api.getNationalMetrics();
      window.State.set({ nationalMetrics: data });
      this.renderTicker(data);
    } catch (err) {
      console.error('Error fetching metrics:', err);
    }
  },

  renderTicker(data) {
    if (!data) return;
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    setVal('tickerReportingFacs', `${data.facilities_reporting}/${data.facilities_total}`);
    setVal('tickerBedOccupancy', `${data.bed_occupancy_rate}%`);
    setVal('tickerIcuPressure', `${data.icu_occupancy_rate}%`);
    setVal('tickerWorkforce', `${data.workforce_coverage_pct}%`);
    setVal('tickerCriticalStockouts', data.critical_stockouts_count);
    setVal('tickerEmergencyAlerts', data.emergency_alerts);
    setVal('tickerPendingApprovals', data.pending_recommendations);
    setVal('tickerDataQuality', `${data.national_data_quality_score}%`);

    // Nav badges
    const badgeRecs = document.getElementById('navRecsBadge');
    if (badgeRecs) badgeRecs.innerText = data.pending_recommendations;

    const badgeStock = document.getElementById('navStockAlertsBadge');
    if (badgeStock) badgeStock.innerText = data.critical_stockouts_count;
  },

  async loadFacilities() {
    try {
      const districtId = window.State.get().selectedDistrict;
      const type = window.State.get().selectedFacilityType;
      const facilities = await window.Api.getFacilities({ district_id: districtId, type: type });
      
      if (window.mapInstance) {
        window.mapInstance.setFacilities(facilities);
      }

      // Also render map side list
      const listContainer = document.getElementById('mapFacilityList');
      if (listContainer) {
        listContainer.innerHTML = facilities.map(f => `
          <div class="card" style="padding:10px 14px;cursor:pointer;background:rgba(15,23,42,0.6);" onclick="App.openFacilityInspector('${f.facility_id}')">
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <span style="font-weight:600;font-size:13px;color:#f8fafc;">${f.name}</span>
              <span class="badge ${f.active_alerts_count > 0 ? 'badge-danger' : 'badge-normal'}">${f.facility_type}</span>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px;display:flex;justify-content:space-between;">
              <span>${f.district_name}</span>
              <span>Beds: ${f.occupied_beds}/${f.total_beds}</span>
            </div>
          </div>
        `).join('');
      }
    } catch (err) {
      console.error('Error loading facilities:', err);
    }
  },

  async populateFilterDropdowns() {
    try {
      const hierarchy = await window.Api.getHierarchy();
      const districtSelect = document.getElementById('filterDistrictSelect');
      const simDistrictSelect = document.getElementById('simDistrictSelect');
      const txFacSelect = document.getElementById('txFacilitySelect');
      const offFacSelect = document.getElementById('offlineFacilitySelect');

      let districtOptions = '<option value="">All Districts (National)</option>';
      let facilityOptions = '';

      hierarchy.forEach(reg => {
        (reg.districts || []).forEach(d => {
          districtOptions += `<option value="${d.district_id}">${d.name} (${reg.code})</option>`;
          (d.facilities || []).forEach(f => {
            facilityOptions += `<option value="${f.facility_id}">${f.name} (${f.facility_type})</option>`;
          });
        });
      });

      if (districtSelect && districtSelect.children.length <= 1) districtSelect.innerHTML = districtOptions;
      if (simDistrictSelect && simDistrictSelect.children.length <= 1) simDistrictSelect.innerHTML = districtOptions;
      if (txFacSelect) txFacSelect.innerHTML = facilityOptions;
      if (offFacSelect) offFacSelect.innerHTML = facilityOptions;

      // Populate products
      const products = await window.Api.getProducts();
      let prodOptions = '';
      products.forEach(p => {
        prodOptions += `<option value="${p.product_id}">${p.generic_name} (${p.category})</option>`;
      });
      const txProdSelect = document.getElementById('txProductSelect');
      const offProdSelect = document.getElementById('offlineProductSelect');
      const predProdSelect = document.getElementById('predProductSelect');
      if (txProdSelect) txProdSelect.innerHTML = prodOptions;
      if (offProdSelect) offProdSelect.innerHTML = prodOptions;
      if (predProdSelect && predProdSelect.children.length <= 1) predProdSelect.innerHTML = prodOptions;

    } catch (err) {
      console.error('Error populating filters:', err);
    }
  },

  async openFacilityInspector(facilityId) {
    try {
      const data = await window.Api.getFacilityDetail(facilityId);
      if (!data) return;

      const drawer = document.getElementById('facilityInspectorDrawer');
      if (!drawer) return;

      document.getElementById('inspFacName').innerText = data.name;
      document.getElementById('inspFacType').innerText = `${data.facility_type} • ${data.district_name} (${data.region_name})`;
      document.getElementById('inspFacStatus').innerText = `Status: ${data.operational_status} | Connectivity: ${data.connectivity_status}`;
      document.getElementById('inspDqScore').innerText = `${data.data_quality_score}%`;
      document.getElementById('inspCatchment').innerText = (data.catchment_population || 0).toLocaleString();

      // Beds
      const b = data.bed_status;
      if (b && b.total_beds > 0) {
        document.getElementById('inspBedsOccupied').innerText = `${b.occupied_beds} / ${b.total_beds} (${Math.round((b.occupied_beds/b.total_beds)*100)}%)`;
        document.getElementById('inspIcuOccupied').innerText = `${b.icu_occupied} / ${b.icu_beds} (${b.icu_beds ? Math.round((b.icu_occupied/b.icu_beds)*100) : 0}%)`;
        document.getElementById('inspOxygenBeds').innerText = `${b.oxygen_occupied} / ${b.oxygen_beds}`;
        document.getElementById('inspVentilators').innerText = `${b.ventilators_in_use} / ${b.ventilators_total}`;
      } else {
        document.getElementById('inspBedsOccupied').innerText = 'N/A (Warehouse)';
        document.getElementById('inspIcuOccupied').innerText = 'N/A';
        document.getElementById('inspOxygenBeds').innerText = 'N/A';
        document.getElementById('inspVentilators').innerText = 'N/A';
      }

      // Batches
      const batches = await window.Api.getFacilityBatches(facilityId);
      const batchTbody = document.getElementById('inspBatchesTableBody');
      if (batchTbody) {
        batchTbody.innerHTML = batches.slice(0, 8).map(b => `
          <tr>
            <td><b>${b.generic_name}</b></td>
            <td><code>${b.batch_number}</code></td>
            <td><b>${b.available_quantity}</b></td>
            <td>${b.expiry_date}</td>
            <td><span class="badge ${b.expiry_badge}">${b.expiry_status}</span></td>
          </tr>
        `).join('') || '<tr><td colspan="5">No stock batches found.</td></tr>';
      }

      // Alerts
      const alertsContainer = document.getElementById('inspAlertsList');
      if (alertsContainer) {
        alertsContainer.innerHTML = (data.alerts || []).map(a => `
          <div style="padding:8px 12px;background:rgba(15,23,42,0.8);border-left:3px solid #ef4444;border-radius:4px;margin-bottom:6px;">
            <div style="display:flex;justify-content:space-between;font-size:11px;">
              <span class="badge badge-danger">${a.severity}</span>
              <span style="color:#94a3b8;">${a.detected_at}</span>
            </div>
            <div style="font-size:12px;color:#f8fafc;margin-top:4px;font-weight:600;">${a.resource_name}</div>
            <div style="font-size:11px;color:#cbd5e1;">${a.reason}</div>
          </div>
        `).join('') || '<div style="color:#94a3b8;font-size:12px;">No active alerts for this facility.</div>';
      }

      drawer.classList.add('active');
    } catch (err) {
      console.error('Error opening inspector:', err);
    }
  },

  // ----------------- Inventory View -----------------
  async loadInventoryView() {
    try {
      const did = window.State.get().selectedDistrict;
      const data = await window.Api.getInventory({ district_id: did });
      const tbody = document.getElementById('inventoryTableBody');
      if (!tbody) return;

      tbody.innerHTML = data.slice(0, 35).map(item => `
        <tr>
          <td>
            <div style="font-weight:600;color:#f8fafc;">${item.generic_name}</div>
            <div style="font-size:11px;color:#64748b;">${item.product_code} • ${item.category}</div>
          </td>
          <td>
            <div style="font-weight:500;">${item.facility_name}</div>
            <div style="font-size:11px;color:#94a3b8;">${item.facility_type} (${item.district_name})</div>
          </td>
          <td><b>${item.available_quantity}</b> ${item.unit_of_measure}</td>
          <td>${item.avg_daily_consumption}/day</td>
          <td>
            <div class="progress-bar-container">
              <div style="display:flex;justify-content:space-between;font-size:11px;">
                <span style="font-weight:700;">${item.days_of_stock}d</span>
                <span style="color:#94a3b8;">ROP: ${item.reorder_point}</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" style="width:${Math.min(100, item.days_of_stock * 3.5)}%;background:${item.risk_level === 'CRITICAL' ? '#ef4444' : (item.risk_level === 'WARNING' ? '#f97316' : (item.risk_level === 'WATCH' ? '#f59e0b' : '#10b981'))};"></div>
              </div>
            </div>
          </td>
          <td><span class="badge ${item.risk_class}">● ${item.risk_level}</span></td>
          <td>
            <button class="btn btn-outline btn-sm" onclick="App.openFacilityInspector('${item.facility_id}')">Inspect</button>
          </td>
        </tr>
      `).join('');

      // Also load FEFO expiries
      const expiries = await window.Api.getFefoExpiries(35);
      const fefoTbody = document.getElementById('fefoTableBody');
      if (fefoTbody) {
        fefoTbody.innerHTML = expiries.slice(0, 10).map(e => `
          <tr>
            <td><b>${e.generic_name}</b></td>
            <td>${e.facility_name}</td>
            <td><code>${e.batch_number}</code></td>
            <td><b style="color:#ef4444;">${e.available_quantity}</b></td>
            <td>${e.expiry_date}</td>
            <td><span class="badge ${e.days_to_expiry <= 14 ? 'badge-fefo-urgent' : 'badge-warning'}">${e.days_to_expiry} days</span></td>
            <td>
              <button class="btn btn-outline btn-sm" onclick="App.promptTransfer('${e.facility_id}', '${e.product_id}', ${e.available_quantity})">Redistribute</button>
            </td>
          </tr>
        `).join('') || '<tr><td colspan="7">No batches near expiry threshold.</td></tr>';
      }

    } catch (err) {
      console.error('Error loading inventory view:', err);
    }
  },

  async handleCreateTransaction() {
    const fid = document.getElementById('txFacilitySelect').value;
    const pid = document.getElementById('txProductSelect').value;
    const txType = document.getElementById('txTypeSelect').value;
    const qty = parseInt(document.getElementById('txQtyInput').value);
    const refDoc = document.getElementById('txRefInput').value;
    const notes = document.getElementById('txNotesInput').value;

    try {
      const res = await window.Api.postTransaction({
        facility_id: fid,
        product_id: pid,
        transaction_type: txType,
        quantity: qty,
        reference_doc: refDoc,
        notes: notes,
        created_by: window.State.get().currentUser
      });

      this.showToast(`Transaction posted! ${txType} ${qty} units. New balance: ${res.new_balance}`, 'success');
      document.getElementById('modalTransaction').classList.remove('active');
      this.loadInventoryView();
      this.fetchMetrics();
    } catch (err) {
      this.showToast(`Transaction failed: ${err.message}`, 'error');
    }
  },

  // ----------------- Capacity View -----------------
  async loadCapacityView() {
    try {
      const did = window.State.get().selectedDistrict;
      const beds = await window.Api.getBeds({ district_id: did });
      const tbody = document.getElementById('capacityTableBody');
      if (!tbody) return;

      tbody.innerHTML = beds.map(b => `
        <tr>
          <td>
            <div style="font-weight:600;color:#f8fafc;">${b.facility_name}</div>
            <div style="font-size:11px;color:#94a3b8;">${b.facility_type} (${b.district_name})</div>
          </td>
          <td><b>${b.occupied_beds}</b> / ${b.functional_beds}</td>
          <td>
            <div class="progress-bar-container">
              <span style="font-size:11px;font-weight:700;">${b.occupancy_rate}%</span>
              <div class="progress-track">
                <div class="progress-fill" style="width:${Math.min(100, b.occupancy_rate)}%;background:${b.occupancy_rate >= 90 ? '#ef4444' : (b.occupancy_rate >= 75 ? '#f59e0b' : '#10b981')};"></div>
              </div>
            </div>
          </td>
          <td>
            <span style="font-weight:600;color:${b.icu_occupancy_rate >= 90 ? '#ef4444' : '#f8fafc'};">${b.icu_occupied}/${b.icu_beds} (${b.icu_occupancy_rate}%)</span>
          </td>
          <td>${b.oxygen_occupied}/${b.oxygen_beds}</td>
          <td><b>${b.operational_staffed_capacity}</b> beds</td>
          <td><span class="badge ${b.pressure_badge}">● ${b.pressure_status}</span></td>
        </tr>
      `).join('');

      // Also load workforce
      const wf = await window.Api.getWorkforce({ district_id: did });
      const wfTbody = document.getElementById('workforceTableBody');
      if (wfTbody) {
        wfTbody.innerHTML = wf.slice(0, 25).map(w => `
          <tr>
            <td>${w.facility_name}</td>
            <td><b>${w.role_type}</b></td>
            <td>${w.scheduled_count}</td>
            <td><b style="color:#34d399;">${w.present_count}</b></td>
            <td><span style="color:${w.shortage_headcount > 0 ? '#ef4444' : '#64748b'};">${w.shortage_headcount}</span></td>
            <td>${w.coverage_rate}%</td>
            <td><span class="badge ${w.badge_class}">${w.shortage_severity}</span></td>
          </tr>
        `).join('');
      }

    } catch (err) {
      console.error('Error loading capacity view:', err);
    }
  },

  // ----------------- Predictions View -----------------
  async loadPredictionsView() {
    try {
      const fid = document.getElementById('predFacilitySelect')?.value || 'FAC-001';
      const pid = document.getElementById('predProductSelect')?.value || 'MED-001';

      // 1. Demand Forecast
      const forecast = await window.Api.getForecast(fid, pid, 30);
      window.Charts.renderForecastChart('demandForecastChart', forecast);

      document.getElementById('forecastModelMeta').innerText = `Model: ${forecast.provenance.model_id} (${forecast.provenance.model_version}) | WAPE: ${forecast.provenance.calibration_wape} | Generated: ${forecast.provenance.generated_at}`;
      document.getElementById('forecastBurnRate').innerText = `${forecast.avg_daily_consumption} units/day`;
      document.getElementById('forecastStockoutDate').innerText = forecast.expected_stockout_date || 'No Stockout Projected (>30d)';

      // 2. Stockout Hazards Table
      const did = window.State.get().selectedDistrict;
      const predictions = await window.Api.getStockoutPredictions({ district_id: did });
      const tbody = document.getElementById('stockoutTableBody');
      if (tbody) {
        tbody.innerHTML = predictions.slice(0, 15).map(p => `
          <tr>
            <td>
              <div style="font-weight:600;color:var(--text-main, #0f172a);">${p.generic_name}</div>
              <div style="font-size:11px;color:var(--text-muted, #475569);">${p.facility_name}</div>
            </td>
            <td><b>${p.available_stock}</b></td>
            <td><b>${p.days_of_stock}d</b> (Lead: ${p.lead_time_days}d)</td>
            <td><b style="color:${p.p_stockout_7d > 0.6 ? '#dc2626' : 'var(--text-main, #0f172a)'};">${Math.round(p.p_stockout_7d * 100)}%</b></td>
            <td><b>${Math.round(p.p_stockout_14d * 100)}%</b></td>
            <td><span class="badge ${p.badge_class}">● ${p.risk_tier}</span></td>
            <td><span style="font-size:11px;color:var(--text-muted, #475569);">${p.explainability_drivers[0]}</span></td>
          </tr>
        `).join('');
      }

      // 3. Syndromic Anomalies
      const anomalies = await window.Api.getAnomalies();
      const anomalyContainer = document.getElementById('anomaliesList');
      if (anomalyContainer) {
        anomalyContainer.innerHTML = anomalies.map(a => `
          <div class="card" style="padding:12px;margin-bottom:8px;background:#ffffff;border:1px solid #e2e8f0;border-left:3px solid ${a.severity === 'CRITICAL' ? '#dc2626' : '#d97706'};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-weight:700;font-size:13px;color:#0f172a;">${a.facility_name} • ${a.resource_name}</span>
              <span class="badge ${a.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}">z-score: ${a.z_score}</span>
            </div>
            <div style="font-size:12px;color:#475569;margin-top:4px;">
              Baseline: <b>${a.baseline_value}</b> ➔ Observed: <b style="color:#dc2626;">${a.observed_value}</b> (${a.deviation_pct})
            </div>
            <div style="font-size:12px;color:#334155;margin-top:6px;">${a.explanation}</div>
          </div>
        `).join('') || '<div style="color:var(--text-muted, #475569);font-size:12px;">No active epidemiological anomalies detected.</div>';
      }

    } catch (err) {
      console.error('Error loading predictions view:', err);
    }
  },

  // ----------------- Recommendations & Approvals -----------------
  async loadRecommendationsView() {
    try {
      const recs = await window.Api.getRecommendations();
      const container = document.getElementById('recommendationsList');
      if (!container) return;

      const userRole = (window.State.get().currentRole || '').toUpperCase();
      const canApprove = ['ADMIN', 'HEALTH_OFFICER'].includes(userRole);

      container.innerHTML = recs.map(r => `
        <div class="rec-card ${r.priority === 'URGENT' ? 'rec-urgent' : (r.priority === 'HIGH' ? 'rec-high' : '')}">
          <div class="rec-header">
            <div class="rec-route">
              <span>${r.source_facility_name}</span>
              <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
              </svg>
              <span>${r.dest_facility_name}</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="badge ${r.priority === 'URGENT' ? 'badge-danger' : 'badge-warning'}">${r.priority}</span>
              <span class="badge ${r.status === 'APPROVED' ? 'badge-normal' : (r.status === 'REJECTED' ? 'badge-danger' : 'badge-watch')}">${r.status}</span>
            </div>
          </div>

          <div style="display:flex;gap:20px;font-size:13px;color:#0f172a;background:#f8fafc;border:1px solid #e2e8f0;padding:12px 16px;border-radius:8px;">
            <div>Medicine: <b style="color:#0284c7;">${r.product_name}</b></div>
            <div>Quantity: <b style="color:#059669;">${r.quantity} ${r.unit_of_measure || 'units'}</b></div>
            <div>Coverage Effect: <b>${r.current_dest_days_stock}d ➔ ${r.expected_dest_days_stock}d</b></div>
            <div>Confidence: <b style="color:#7c3aed;">${Math.round(r.confidence * 100)}%</b></div>
          </div>

          <div class="rec-reasons">
            <div style="font-weight:700;font-size:11px;color:#475569;margin-bottom:4px;text-transform:uppercase;">Explainable AI Rationale ("WHY?"):</div>
            <ul>
              ${(r.reason_list_parsed || []).map(reason => `<li>${reason}</li>`).join('')}
            </ul>
          </div>

          <div class="rec-footer">
            <div class="rec-meta">
              <span>ID: <code style="color:#0d9488;">${r.recommendation_id}</code></span>
              <span>Assumptions: ${r.assumptions || 'Cold box certified.'}</span>
              ${r.approved_by ? `<span style="color:#059669;font-weight:600;">Actioned by: ${r.approved_by}</span>` : ''}
            </div>
            ${r.status === 'AWAITING_APPROVAL' ? (
              canApprove ? `
                <div style="display:flex;gap:8px;">
                  <button class="btn btn-danger btn-sm" onclick="App.handleRejectRecommendation('${r.recommendation_id}')">Reject</button>
                  <button class="btn btn-success btn-sm" onclick="App.handleApproveRecommendation('${r.recommendation_id}')">Approve & Dispatch</button>
                </div>
              ` : `
                <div style="display:flex;gap:8px;align-items:center;">
                  <span class="badge" style="background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1;font-size:11px;padding:4px 8px;" title="Action restricted to District Health Officer or National Admin">
                    🔒 Approval Locked (Requires Health Officer or Admin)
                  </span>
                </div>
              `
            ) : `<span style="font-size:12px;color:#64748b;">Decision Archived</span>`}
          </div>
        </div>
      `).join('') || '<div style="color:#64748b;padding:24px;text-align:center;">No pending recommendations. Network is balanced.</div>';

    } catch (err) {
      console.error('Error loading recommendations view:', err);
    }
  },

  async handleApproveRecommendation(recId) {
    const userRole = (window.State.get().currentRole || '').toUpperCase();
    if (!['ADMIN', 'HEALTH_OFFICER'].includes(userRole)) {
      this.showToast(`Access Denied (403): Role '${userRole}' cannot approve redistribution orders. Requires District Health Officer or Admin.`, 'error');
      return;
    }

    const notes = prompt('Enter approval verification notes (or leave default):', 'Approved for immediate emergency dispatch');
    if (notes === null) return;

    try {
      const res = await window.Api.approveRecommendation(recId, notes, window.State.get().currentUser);
      this.showToast(`Transfer order committed! ${res.transfer_quantity} units dispatched.`, 'success');
      this.loadRecommendationsView();
      this.fetchMetrics();
    } catch (err) {
      this.showToast(`Approval failed: ${err.message}`, 'error');
    }
  },

  async handleRejectRecommendation(recId) {
    const userRole = (window.State.get().currentRole || '').toUpperCase();
    if (!['ADMIN', 'HEALTH_OFFICER'].includes(userRole)) {
      this.showToast(`Access Denied (403): Role '${userRole}' cannot reject redistribution orders. Requires District Health Officer or Admin.`, 'error');
      return;
    }

    const notes = prompt('Enter justification for rejecting AI recommendation:', 'Clinical priority override / local supply adequate');
    if (notes === null) return;

    try {
      await window.Api.rejectRecommendation(recId, notes, window.State.get().currentUser);
      this.showToast('Recommendation rejected and archived to audit log.', 'info');
      this.loadRecommendationsView();
      this.fetchMetrics();
    } catch (err) {
      this.showToast(`Rejection failed: ${err.message}`, 'error');
    }
  },

  // ----------------- Audit View -----------------
  async loadAuditView() {
    try {
      const logs = await window.Api.getAuditLogs(35);
      const tbody = document.getElementById('auditTableBody');
      if (!tbody) return;

      tbody.innerHTML = logs.map(l => `
        <tr>
          <td><code style="color:#64748b;font-size:11px;">${l.created_at}</code></td>
          <td><b>${l.user_name}</b> <div style="font-size:10px;color:#64748b;">${l.user_role}</div></td>
          <td><span class="badge" style="background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;">${l.action_type}</span></td>
          <td>${l.description}</td>
          <td><code style="color:#0f766e;font-size:11px;font-weight:600;">${l.tamper_hash.substr(0, 16)}...</code></td>
        </tr>
      `).join('');
    } catch (err) {
      console.error('Error loading audit view:', err);
    }
  },

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    const borderCol = type === 'success' ? '#0d9488' : (type === 'error' ? '#ef4444' : (type === 'warning' ? '#f59e0b' : '#0284c7'));
    toast.style.borderLeft = `4px solid ${borderCol}`;
    toast.innerHTML = `
      <div style="flex:1;color:#0f172a;font-weight:500;">${message}</div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

window.App = App;

document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
