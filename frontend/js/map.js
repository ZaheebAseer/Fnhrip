// Interactive National GIS Vector Map
class NationalMap {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.facilities = [];
    this.hoveredFacility = null;
    this.animationFrame = null;
    this.pulseAngle = 0;
    this.activeLayer = 'ALL';

    this.initCanvas();
    this.bindEvents();
    this.startAnimation();
  }

  initCanvas() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.width = rect.width || 800;
    this.height = rect.height || 540;
    this.canvas.width = this.width * window.devicePixelRatio;
    this.canvas.height = this.height * window.devicePixelRatio;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  }

  bindEvents() {
    window.addEventListener('resize', () => {
      if (this.canvas) {
        this.initCanvas();
        this.draw();
      }
    });

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      let found = null;
      for (const fac of this.facilities) {
        const pt = this.project(fac.latitude, fac.longitude);
        const dist = Math.hypot(pt.x - mouseX, pt.y - mouseY);
        if (dist <= 14) {
          found = fac;
          break;
        }
      }
      this.hoveredFacility = found;
      this.canvas.style.cursor = found ? 'pointer' : 'default';
    });

    this.canvas.addEventListener('click', () => {
      if (this.hoveredFacility) {
        window.App.openFacilityInspector(this.hoveredFacility.facility_id);
      }
    });
  }

  setFacilities(facilities) {
    this.facilities = facilities;
    this.draw();
  }

  setLayer(layer) {
    this.activeLayer = layer;
    this.draw();
  }

  // Geographic projection from Lat/Long to Canvas coordinates
  project(lat, lng) {
    // Lat range roughly 18.8 to 30.6
    // Lng range roughly 72.8 to 78.3
    const minLat = 18.5, maxLat = 30.8;
    const minLng = 72.5, maxLng = 78.5;

    const x = ((lng - minLng) / (maxLng - minLng)) * (this.width - 120) + 60;
    // Invert Y for canvas coordinates
    const y = (1.0 - ((lat - minLat) / (maxLat - minLat))) * (this.height - 100) + 50;

    return { x, y };
  }

  startAnimation() {
    const loop = () => {
      this.pulseAngle = (this.pulseAngle + 0.05) % (Math.PI * 2);
      this.draw();
      this.animationFrame = requestAnimationFrame(loop);
    };
    this.animationFrame = requestAnimationFrame(loop);
  }

  draw() {
    if (!this.ctx) return;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    // 1. Dark background terrain grid
    this.drawBackgroundGrid(ctx);

    // 2. Draw Region Boundaries & River Delta
    this.drawGeoTerrain(ctx);

    // 3. Draw Inter-facility Active Redistribution Routes
    this.drawTransportRoutes(ctx);

    // 4. Draw Facilities
    this.drawFacilities(ctx);

    // 5. Draw Tooltip if hovering
    if (this.hoveredFacility) {
      this.drawTooltip(ctx, this.hoveredFacility);
    }
  }

  drawBackgroundGrid(ctx) {
    ctx.strokeStyle = 'rgba(15, 23, 42, 0.04)';
    ctx.lineWidth = 1;
    const gridSize = 40;
    for (let x = 0; x < this.width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, this.height);
      ctx.stroke();
    }
    for (let y = 0; y < this.height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(this.width, y);
      ctx.stroke();
    }
  }

  drawGeoTerrain(ctx) {
    // Regional polygon boundaries
    ctx.fillStyle = 'rgba(13, 148, 136, 0.04)';
    ctx.strokeStyle = 'rgba(13, 148, 136, 0.18)';
    ctx.lineWidth = 1.5;

    // Northern Highlands zone
    ctx.beginPath();
    ctx.ellipse(this.width * 0.75, this.height * 0.25, 140, 90, -0.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Central Metro zone
    ctx.beginPath();
    ctx.ellipse(this.width * 0.65, this.height * 0.48, 120, 80, 0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Coastal River Delta zone
    ctx.beginPath();
    ctx.ellipse(this.width * 0.25, this.height * 0.8, 130, 75, 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // River corridor line
    ctx.strokeStyle = 'rgba(2, 132, 199, 0.28)';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(this.width * 0.85, 40);
    ctx.bezierCurveTo(this.width * 0.6, this.height * 0.35, this.width * 0.4, this.height * 0.6, this.width * 0.15, this.height * 0.95);
    ctx.stroke();
  }

  drawTransportRoutes(ctx) {
    // Active routes (e.g. NEMD-1 -> Highland PHC; Port Logistics -> Delta Island)
    const facMap = {};
    this.facilities.forEach(f => { facMap[f.facility_id] = f; });

    const activeRoutes = [
      { from: 'FAC-002', to: 'FAC-010', color: '#3b82f6', label: 'Hill Express Route (Cold Chain)' },
      { from: 'FAC-016', to: 'FAC-020', color: '#06b6d4', label: 'Delta Waterway Barge' },
      { from: 'FAC-001', to: 'FAC-004', color: '#10b981', label: 'Urban Rapid Shuttle' }
    ];

    activeRoutes.forEach(r => {
      const f1 = facMap[r.from];
      const f2 = facMap[r.to];
      if (f1 && f2) {
        const p1 = this.project(f1.latitude, f1.longitude);
        const p2 = this.project(f2.latitude, f2.longitude);

        ctx.strokeStyle = r.color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);

        const midX = (p1.x + p2.x) / 2 - 30;
        const midY = (p1.y + p2.y) / 2 - 20;

        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Animated transit pulse dot along curve
        const t = (Math.sin(this.pulseAngle) + 1) / 2;
        const curX = (1 - t) * (1 - t) * p1.x + 2 * (1 - t) * t * midX + t * t * p2.x;
        const curY = (1 - t) * (1 - t) * p1.y + 2 * (1 - t) * t * midY + t * t * p2.y;

        ctx.fillStyle = '#ffffff';
        ctx.shadowColor = r.color;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(curX, curY, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    });
  }

  drawFacilities(ctx) {
    this.facilities.forEach(fac => {
      // Filter layer check
      if (this.activeLayer === 'HOSPITALS' && !fac.facility_type.includes('Hospital') && fac.facility_type !== 'Medical College') return;
      if (this.activeLayer === 'WAREHOUSES' && fac.facility_type !== 'Warehouse') return;
      if (this.activeLayer === 'RISK_STOCK' && fac.active_alerts_count === 0 && fac.operational_status === 'ACTIVE') return;
      if (this.activeLayer === 'ICU_STRESS' && (fac.icu_beds === 0 || (fac.icu_occupied / fac.icu_beds < 0.85))) return;

      const pt = this.project(fac.latitude, fac.longitude);

      // Determine color by risk & operational status
      let color = '#10b981'; // normal
      let pulseColor = 'rgba(16, 185, 129, 0.4)';
      let isSevere = false;

      if (fac.operational_status === 'DEGRADED' || fac.connectivity_status === 'OFFLINE') {
        color = '#ef4444';
        pulseColor = 'rgba(239, 68, 68, 0.6)';
        isSevere = true;
      } else if (fac.facility_id === 'FAC-001') { // Critical ICU emergency
        color = '#a855f7';
        pulseColor = 'rgba(168, 85, 247, 0.7)';
        isSevere = true;
      } else if (fac.active_alerts_count > 0 || fac.facility_id === 'FAC-010') {
        color = '#f97316';
        pulseColor = 'rgba(249, 115, 22, 0.5)';
        isSevere = true;
      }

      // Warehouse distinctive diamond shape
      const isWarehouse = fac.facility_type === 'Warehouse';

      // Pulse ring for severe facilities
      if (isSevere) {
        const pulseR = 8 + Math.sin(this.pulseAngle * 1.5) * 6;
        ctx.strokeStyle = pulseColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, pulseR, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw Node
      ctx.shadowColor = color;
      ctx.shadowBlur = 10;
      ctx.fillStyle = color;

      if (isWarehouse) {
        // Diamond
        const size = 9;
        ctx.beginPath();
        ctx.moveTo(pt.x, pt.y - size);
        ctx.lineTo(pt.x + size, pt.y);
        ctx.lineTo(pt.x, pt.y + size);
        ctx.lineTo(pt.x - size, pt.y);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();
      } else {
        // Circle
        const radius = fac.facility_type === 'Medical College' ? 8 : (fac.facility_type === 'District Hospital' ? 6.5 : 5);
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.shadowBlur = 0;

      // Label
      ctx.fillStyle = '#334155';
      ctx.font = '600 10px Outfit, sans-serif';
      ctx.fillText(fac.code, pt.x + 10, pt.y + 3);
    });
  }

  drawTooltip(ctx, fac) {
    const pt = this.project(fac.latitude, fac.longitude);
    const boxW = 210;
    const boxH = 92;
    const boxX = Math.min(this.width - boxW - 15, pt.x + 14);
    const boxY = Math.max(15, pt.y - 45);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.98)';
    ctx.strokeStyle = 'rgba(13, 148, 136, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = 'rgba(15, 23, 42, 0.12)';
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 8);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.fillStyle = '#0f172a';
    ctx.font = 'bold 12px Outfit, sans-serif';
    ctx.fillText(fac.name.length > 24 ? fac.name.substr(0, 24) + '...' : fac.name, boxX + 12, boxY + 20);

    ctx.fillStyle = '#475569';
    ctx.font = '11px Outfit, sans-serif';
    ctx.fillText(`Type: ${fac.facility_type} | ${fac.district_name}`, boxX + 12, boxY + 36);

    const bedsText = fac.total_beds > 0 ? `${fac.occupied_beds}/${fac.total_beds} Beds (${Math.round((fac.occupied_beds/fac.total_beds)*100)}%)` : 'Supply Depot (No Inpatient)';
    ctx.fillText(`Capacity: ${bedsText}`, boxX + 12, boxY + 52);

    const statusColor = fac.connectivity_status === 'ONLINE' ? '#059669' : '#dc2626';
    ctx.fillStyle = statusColor;
    ctx.fillText(`● ${fac.connectivity_status} | DQ Score: ${fac.data_quality_score}%`, boxX + 12, boxY + 70);

    ctx.fillStyle = '#0d9488';
    ctx.font = 'bold italic 10px Outfit, sans-serif';
    ctx.fillText('Click to inspect facility →', boxX + 12, boxY + 84);
  }
}

window.NationalMap = NationalMap;
