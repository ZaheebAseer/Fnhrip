// What-If Emergency Simulator Controller
const Simulator = {
  init() {
    this.bindControls();
    // Run initial baseline simulation
    this.run();
  },

  bindControls() {
    const surgeSlider = document.getElementById('simSurgeSlider');
    const surgeVal = document.getElementById('simSurgeVal');
    if (surgeSlider && surgeVal) {
      surgeSlider.addEventListener('input', (e) => {
        surgeVal.innerText = `+${e.target.value}%`;
      });
    }

    const supplySlider = document.getElementById('simSupplyCutSlider');
    const supplyVal = document.getElementById('simSupplyCutVal');
    if (supplySlider && supplyVal) {
      supplySlider.addEventListener('input', (e) => {
        supplyVal.innerText = `-${e.target.value}%`;
      });
    }

    const staffSlider = document.getElementById('simStaffLossSlider');
    const staffVal = document.getElementById('simStaffLossVal');
    if (staffSlider && staffVal) {
      staffSlider.addEventListener('input', (e) => {
        staffVal.innerText = `-${e.target.value}%`;
      });
    }

    const runBtn = document.getElementById('btnRunSimulation');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.run());
    }

    const resetBtn = document.getElementById('btnResetSimulation');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (surgeSlider) { surgeSlider.value = 30; surgeVal.innerText = '+30%'; }
        if (supplySlider) { supplySlider.value = 20; supplyVal.innerText = '-20%'; }
        if (staffSlider) { staffSlider.value = 15; staffVal.innerText = '-15%'; }
        const wh = document.getElementById('simWarehouseSelect');
        if (wh) wh.value = '';
        this.run();
      });
    }
  },

  async run() {
    const role = (window.State?.get()?.currentRole || '').toUpperCase();
    if (!['ADMIN', 'HEALTH_OFFICER', 'ML_ENGINEER'].includes(role)) {
      window.App.showToast(`Access Denied (403): Role '${role}' cannot run emergency simulations. Requires ML Engineer, Health Officer, or Admin.`, 'error');
      return;
    }

    const surge = parseInt(document.getElementById('simSurgeSlider')?.value || 30);
    const supplyCut = parseInt(document.getElementById('simSupplyCutSlider')?.value || 20);
    const staffLoss = parseInt(document.getElementById('simStaffLossSlider')?.value || 15);
    const whOutage = document.getElementById('simWarehouseSelect')?.value || null;

    const runBtn = document.getElementById('btnRunSimulation');
    if (runBtn) {
      runBtn.innerText = 'Calculating Impact...';
      runBtn.disabled = true;
    }

    try {
      const data = await window.Api.runSimulation({
        epidemic_surge_pct: surge,
        supply_cut_pct: supplyCut,
        warehouse_outage_id: whOutage,
        workforce_absenteeism_pct: staffLoss
      });

      this.renderResults(data);
    } catch (err) {
      console.error('Simulation error:', err);
      window.App.showToast(`Simulation failed: ${err.message}`, 'error');
    } finally {
      if (runBtn) {
        runBtn.innerText = 'Simulate Emergency Scenario';
        runBtn.disabled = false;
      }
    }
  },

  renderResults(data) {
    const res = data.simulation_results;
    if (!res) return;

    // Time to critical state
    const timeEl = document.getElementById('simTimeToCritical');
    if (timeEl) {
      timeEl.innerText = `${res.time_to_critical_state_days} Days`;
      timeEl.className = res.time_to_critical_state_days <= 3.0 ? 'ticker-val text-danger' : 'ticker-val text-warning';
    }

    // Bed Occupancy
    const bedGaugeContainer = document.getElementById('simBedGauge');
    if (bedGaugeContainer) {
      const color = res.simulated_bed_occupancy_pct >= 90 ? '#ef4444' : (res.simulated_bed_occupancy_pct >= 80 ? '#f59e0b' : '#10b981');
      window.Charts.renderRadialGauge('simBedGauge', Math.round(res.simulated_bed_occupancy_pct), 'Projected Bed Occupancy', color);
    }

    // ICU Saturation
    const icuGaugeContainer = document.getElementById('simIcuGauge');
    if (icuGaugeContainer) {
      const color = res.simulated_icu_occupancy_pct >= 95 ? '#ef4444' : '#f59e0b';
      window.Charts.renderRadialGauge('simIcuGauge', Math.round(res.simulated_icu_occupancy_pct), 'Projected ICU Pressure', color);
    }

    // Deficit metrics
    const bedDeficitEl = document.getElementById('simBedDeficit');
    if (bedDeficitEl) bedDeficitEl.innerText = res.total_bed_deficit > 0 ? `-${res.total_bed_deficit} Beds` : '0 (Buffer OK)';

    const o2ShortageEl = document.getElementById('simO2Shortage');
    if (o2ShortageEl) o2ShortageEl.innerText = res.oxygen_shortage_cylinders > 0 ? `-${res.oxygen_shortage_cylinders} Cylinders` : '0 (Stable)';

    const facsAtRiskEl = document.getElementById('simFacsAtRisk');
    if (facsAtRiskEl) facsAtRiskEl.innerText = `${res.critical_stockout_facilities_count} of ${res.total_facilities_evaluated}`;

    // At-Risk Facilities list
    const atRiskList = document.getElementById('simAtRiskList');
    if (atRiskList) {
      atRiskList.innerHTML = (res.at_risk_facilities || []).map(f => `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#ffffff;border-radius:6px;border:1px solid #e2e8f0;">
          <div>
            <div style="font-weight:600;font-size:12px;color:#0f172a;">${f.facility_name}</div>
            <div style="font-size:11px;color:#64748b;">${f.critical_items_count} critical items exhausted</div>
          </div>
          <span class="badge badge-danger">Failure in ${f.simulated_days_to_failure}d</span>
        </div>
      `).join('') || '<div style="color:#64748b;font-size:12px;">No facilities in immediate failure threshold.</div>';
    }

    // Countermeasures
    const counterList = document.getElementById('simCountermeasuresList');
    if (counterList) {
      counterList.innerHTML = (res.recommended_countermeasures || []).map(c => `
        <li style="margin-bottom:8px;font-size:13px;color:#334155;display:flex;gap:8px;">
          <span style="color:#0d9488;font-weight:700;">▸</span>
          <span>${c}</span>
        </li>
      `).join('');
    }
  }
};

window.Simulator = Simulator;
