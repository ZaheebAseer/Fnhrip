// Offline-First PHC Client Simulator
const OfflineApp = {
  init() {
    this.bindControls();
    this.updateUI();
  },

  bindControls() {
    // Mode toggle button
    const toggleBtn = document.getElementById('btnToggleOfflineMode');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const current = window.State.get().isOfflineMode;
        window.State.set({ isOfflineMode: !current });
        window.App.showToast(!current ? '⚠️ Offline Field Mode Engaged (Transactions will queue locally)' : '🌐 Online Grid Mode Restored', !current ? 'warning' : 'info');
        this.updateUI();
      });
    }

    // Submit offline transaction form
    const offlineTxForm = document.getElementById('offlineTxForm');
    if (offlineTxForm) {
      offlineTxForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.queueTransaction();
      });
    }

    // Sync button
    const syncBtn = document.getElementById('btnSyncOfflineQueue');
    if (syncBtn) {
      syncBtn.addEventListener('click', () => this.syncQueue());
    }
  },

  updateUI() {
    const isOffline = window.State.get().isOfflineMode;
    const queue = window.State.get().offlineQueue || [];

    // Header badge
    const headerStatusBadge = document.getElementById('headerConnectivityBadge');
    if (headerStatusBadge) {
      if (isOffline) {
        headerStatusBadge.innerHTML = `
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444;box-shadow:0 0 6px #ef4444;"></span>
          <span>OFFLINE: ${queue.length} Queued</span>
        `;
        headerStatusBadge.className = 'badge badge-danger';
      } else {
        headerStatusBadge.innerHTML = `
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 6px #10b981;"></span>
          <span>ONLINE: Grid Synced</span>
        `;
        headerStatusBadge.className = 'badge badge-normal';
      }
    }

    // Render Queue Table
    const queueTbody = document.getElementById('offlineQueueTableBody');
    if (queueTbody) {
      if (queue.length === 0) {
        queueTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#64748b;padding:24px;">No queued transactions. Grid is in sync.</td></tr>`;
      } else {
        queueTbody.innerHTML = queue.map((item, idx) => `
          <tr>
            <td><code>${item.action_id}</code></td>
            <td><span class="badge" style="background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;">${item.type}</span></td>
            <td>${item.product_name || item.product_id || 'N/A'}</td>
            <td><b>${item.quantity || 1} units</b></td>
            <td><span style="color:#b45309;font-size:11px;font-weight:600;">PENDING SYNC (${new Date(item.timestamp).toLocaleTimeString()})</span></td>
          </tr>
        `).join('');
      }
    }

    const queueCountBadge = document.getElementById('offlineQueueCountBadge');
    if (queueCountBadge) {
      queueCountBadge.innerText = queue.length;
    }
  },

  queueTransaction() {
    const facId = document.getElementById('offlineFacilitySelect')?.value || 'FAC-010';
    const prodSelect = document.getElementById('offlineProductSelect');
    const prodId = prodSelect?.value || 'MED-001';
    const prodName = prodSelect?.options[prodSelect.selectedIndex]?.text || 'Insulin';
    const qty = parseInt(document.getElementById('offlineQtyInput')?.value || 1);
    const txType = document.getElementById('offlineTxTypeSelect')?.value || 'DISPENSING';
    const notes = document.getElementById('offlineNotesInput')?.value || 'Field clinic dispensing';

    const action = {
      type: 'INVENTORY_TRANSACTION',
      facility_id: facId,
      product_id: prodId,
      product_name: prodName,
      tx_type: txType,
      quantity: qty,
      notes: notes,
      user: window.State.get().currentUser
    };

    window.State.addOfflineAction(action);
    window.App.showToast(`Action queued locally: ${qty} units of ${prodName}`, 'info');
    this.updateUI();

    // Reset inputs
    document.getElementById('offlineQtyInput').value = '1';
    document.getElementById('offlineNotesInput').value = '';
  },

  async syncQueue() {
    const queue = window.State.get().offlineQueue || [];
    if (queue.length === 0) {
      window.App.showToast('Offline queue is empty. Nothing to synchronize.', 'info');
      return;
    }

    const facId = queue[0].facility_id || 'FAC-010';
    const syncBtn = document.getElementById('btnSyncOfflineQueue');
    if (syncBtn) {
      syncBtn.innerText = 'Transmitting Batch...';
      syncBtn.disabled = true;
    }

    try {
      const res = await window.Api.syncOfflineBatch(facId, queue);
      if (res.success) {
        window.State.clearOfflineQueue();
        window.State.set({ isOfflineMode: false });
        window.App.showToast(`Batch sync completed! ${res.applied} actions committed to National Grid.`, 'success');
        this.updateUI();
        window.App.refreshAllData();
      } else {
        window.App.showToast(`Sync failed: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('Offline batch sync error:', err);
      window.App.showToast('Network error during synchronization.', 'error');
    } finally {
      if (syncBtn) {
        syncBtn.innerText = 'Sync to National Grid';
        syncBtn.disabled = false;
      }
    }
  }
};

window.OfflineApp = OfflineApp;
