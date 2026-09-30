// Federated Learning Network & Coordinator Controller
const Federated = {
  async init() {
    await this.loadOverview();
    this.bindControls();
  },

  bindControls() {
    const runRoundBtn = document.getElementById('btnRunFedRound');
    if (runRoundBtn) {
      runRoundBtn.addEventListener('click', () => this.runRound());
    }
  },

  async loadOverview() {
    try {
      const data = await window.Api.getFederatedOverview();
      this.renderOverview(data);
    } catch (err) {
      console.error('Failed to load federated overview:', err);
    }
  },

  renderOverview(data) {
    if (!data) return;

    // Node count & sample stats
    const nodeCountEl = document.getElementById('fedNodeCount');
    if (nodeCountEl) nodeCountEl.innerText = `${data.total_nodes} Sovereign Nodes`;

    const sampleCountEl = document.getElementById('fedSampleCount');
    if (sampleCountEl) sampleCountEl.innerText = `${(data.total_samples_trained / 1000).toFixed(1)}k Records`;

    const avgLossEl = document.getElementById('fedAvgLoss');
    if (avgLossEl) avgLossEl.innerText = data.average_node_loss;

    // Participating nodes cards
    const nodesContainer = document.getElementById('fedNodesList');
    if (nodesContainer && data.participating_nodes) {
      nodesContainer.innerHTML = data.participating_nodes.map(n => `
        <div class="card" style="padding:14px;background:#ffffff;border:1px solid #e2e8f0;box-shadow:var(--shadow-sm);">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <div style="font-weight:700;font-size:13px;color:#0f172a;">${n.country_name}</div>
            <span class="badge badge-normal">● ${n.status}</span>
          </div>
          <div style="font-size:12px;color:#475569;display:flex;justify-content:space-between;margin-top:6px;">
            <span>Node ID: <code style="color:#0284c7;">${n.node_id}</code></span>
            <span>Local Loss: <b style="color:#059669;">${n.last_round_loss}</b></span>
          </div>
          <div style="font-size:11px;color:#64748b;margin-top:4px;">
            Local Training Samples: <b>${n.samples_trained.toLocaleString()}</b> (Data stays local)
          </div>
        </div>
      `).join('');
    }

    // Global models table
    const modelsTbody = document.getElementById('fedModelsTableBody');
    if (modelsTbody && data.global_models) {
      modelsTbody.innerHTML = data.global_models.map(m => `
        <tr>
          <td>
            <div style="font-weight:600;color:#0f172a;">${m.model_name}</div>
            <div style="font-size:11px;color:#64748b;">${m.model_id} • ${m.task_type}</div>
          </td>
          <td><span class="badge" style="background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;">${m.version}</span></td>
          <td><b style="color:#059669;">${(m.accuracy_score * 100).toFixed(1)}%</b></td>
          <td>${m.wape_score}</td>
          <td><code style="color:#7c3aed;">ε = ${m.privacy_budget_epsilon}</code></td>
          <td><span style="font-weight:700;color:#0f172a;">Round #${m.last_aggregation_round}</span></td>
          <td><span class="badge badge-normal">${m.status}</span></td>
        </tr>
      `).join('');
    }

    // Render Convergence chart
    window.Charts.renderConvergenceLine('fedLossChart', [0.12, 0.098, 0.084, 0.071, 0.058, data.average_node_loss]);
  },

  async runRound() {
    const role = (window.State?.get()?.currentRole || '').toUpperCase();
    if (!['ADMIN', 'ML_ENGINEER'].includes(role)) {
      window.App.showToast(`Access Denied (403): Role '${role}' cannot run federated aggregation rounds. Requires ML Engineer or Admin.`, 'error');
      return;
    }

    const btn = document.getElementById('btnRunFedRound');
    if (btn) {
      btn.innerText = 'Transmitting Gradients & Aggregating...';
      btn.disabled = true;
    }

    try {
      const res = await window.Api.runFederatedRound('MOD-DEMAND-01');
      window.App.showToast(`Federated Round #${res.round_completed} Completed! Deployed ${res.new_version}`, 'success');
      await this.loadOverview();
    } catch (err) {
      console.error('Federated round error:', err);
      window.App.showToast(`Federated aggregation failed: ${err.message}`, 'error');
    } finally {
      if (btn) {
        btn.innerText = 'Trigger Federated Aggregation Round';
        btn.disabled = false;
      }
    }
  }
};

window.Federated = Federated;
