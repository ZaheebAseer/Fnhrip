// Lightweight Custom SVG Chart Generator
const Charts = {
  renderForecastChart(containerId, forecastData) {
    const container = document.getElementById(containerId);
    if (!container || !forecastData || !forecastData.forecast_points) return;

    const points = forecastData.forecast_points;
    const width = container.clientWidth || 700;
    const height = 280;
    const padding = { top: 25, right: 35, bottom: 45, left: 55 };

    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;

    // Y domain: from 0 to max(upper_bound) * 1.15
    const maxVal = Math.max(...points.map(p => p.upper_bound), 10) * 1.15;
    const minVal = 0;

    const xScale = (index) => padding.left + (index / (points.length - 1)) * graphWidth;
    const yScale = (val) => padding.top + graphHeight - ((val - minVal) / (maxVal - minVal)) * graphHeight;

    // Build SVG
    let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;overflow:visible;">`;

    // Grid lines
    const yTicks = 5;
    for (let i = 0; i <= yTicks; i++) {
      const val = Math.round((maxVal / yTicks) * i);
      const y = yScale(val);
      svg += `
        <line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="rgba(15,23,42,0.06)" stroke-dasharray="3 3"/>
        <text x="${padding.left - 10}" y="${y + 4}" fill="#64748b" font-size="11" text-anchor="end" font-family="monospace">${val}</text>
      `;
    }

    // Confidence Interval Area Polygon (Upper to Lower bound)
    let areaPath = `M ${xScale(0)} ${yScale(points[0].upper_bound)}`;
    for (let i = 1; i < points.length; i++) {
      areaPath += ` L ${xScale(i)} ${yScale(points[i].upper_bound)}`;
    }
    for (let i = points.length - 1; i >= 0; i--) {
      areaPath += ` L ${xScale(i)} ${yScale(points[i].lower_bound)}`;
    }
    areaPath += ' Z';

    svg += `<path d="${areaPath}" fill="rgba(13, 148, 136, 0.12)" stroke="none" />`;

    // Lower & Upper bound subtle lines
    let upperPath = `M ${xScale(0)} ${yScale(points[0].upper_bound)}`;
    let lowerPath = `M ${xScale(0)} ${yScale(points[0].lower_bound)}`;
    for (let i = 1; i < points.length; i++) {
      upperPath += ` L ${xScale(i)} ${yScale(points[i].upper_bound)}`;
      lowerPath += ` L ${xScale(i)} ${yScale(points[i].lower_bound)}`;
    }
    svg += `<path d="${upperPath}" fill="none" stroke="rgba(13, 148, 136, 0.35)" stroke-dasharray="4 4" stroke-width="1.2" />`;
    svg += `<path d="${lowerPath}" fill="none" stroke="rgba(13, 148, 136, 0.35)" stroke-dasharray="4 4" stroke-width="1.2" />`;

    // Forecast Central Line
    let linePath = `M ${xScale(0)} ${yScale(points[0].forecast_value)}`;
    for (let i = 1; i < points.length; i++) {
      linePath += ` L ${xScale(i)} ${yScale(points[i].forecast_value)}`;
    }
    svg += `<path d="${linePath}" fill="none" stroke="#0d9488" stroke-width="2.5" />`;

    // Data points & X axis labels
    points.forEach((p, idx) => {
      const cx = xScale(idx);
      const cy = yScale(p.forecast_value);
      
      // X ticks every 5 days
      if (idx % 5 === 0 || idx === points.length - 1) {
        svg += `
          <line x1="${cx}" y1="${padding.top + graphHeight}" x2="${cx}" y2="${padding.top + graphHeight + 6}" stroke="rgba(15,23,42,0.15)"/>
          <text x="${cx}" y="${padding.top + graphHeight + 20}" fill="#64748b" font-size="10" text-anchor="middle">Day ${p.day_number}</text>
        `;
      }

      // Stockout marker if reached
      if (p.projected_inventory === 0 && (!points[idx-1] || points[idx-1].projected_inventory > 0)) {
        svg += `
          <line x1="${cx}" y1="${padding.top}" x2="${cx}" y2="${padding.top + graphHeight}" stroke="#ef4444" stroke-dasharray="5 3" stroke-width="2"/>
          <rect x="${cx - 45}" y="${padding.top - 20}" width="90" height="20" rx="4" fill="#ef4444" />
          <text x="${cx}" y="${padding.top - 6}" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">STOCKOUT ⚠️</text>
        `;
      }
    });

    // Legend
    svg += `
      <g transform="translate(${width - 240}, 15)">
        <line x1="0" y1="0" x2="20" y2="0" stroke="#3b82f6" stroke-width="2.5"/>
        <text x="25" y="4" fill="#cbd5e1" font-size="11">Forecast Demand</text>
        <rect x="130" y="-6" width="14" height="12" fill="rgba(59, 130, 246, 0.25)"/>
        <text x="150" y="4" fill="#94a3b8" font-size="11">95% Confidence</text>
      </g>
    `;

    svg += '</svg>';
    container.innerHTML = svg;
  },

  renderRadialGauge(containerId, percentage, label, color = '#3b82f6') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const size = 110;
    const strokeWidth = 9;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const safePct = Math.min(100, Math.max(0, percentage));
    const offset = circumference - (safePct / 100) * circumference;

    container.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;position:relative;width:${size}px;">
        <svg width="${size}" height="${size}" style="transform: rotate(-90deg);">
          <circle cx="${size/2}" cy="${size/2}" r="${radius}" fill="transparent" stroke="#e2e8f0" stroke-width="${strokeWidth}" />
          <circle cx="${size/2}" cy="${size/2}" r="${radius}" fill="transparent" stroke="${color}" stroke-width="${strokeWidth}" 
                  stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round" 
                  style="transition: stroke-dashoffset 0.8s ease;" />
        </svg>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%, -60%);text-align:center;">
          <span style="font-size:18px;font-weight:700;color:#0f172a;font-family:monospace;">${percentage}%</span>
        </div>
        <span style="font-size:11px;color:#64748b;margin-top:6px;font-weight:600;text-align:center;">${label}</span>
      </div>
    `;
  },

  renderConvergenceLine(containerId, historyValues = [0.12, 0.095, 0.082, 0.068, 0.054, 0.048]) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const width = container.clientWidth || 320;
    const height = 90;
    const padding = { top: 10, right: 15, bottom: 20, left: 35 };

    const maxVal = Math.max(...historyValues) * 1.1;
    const minVal = 0;

    const xScale = (idx) => padding.left + (idx / (historyValues.length - 1)) * (width - padding.left - padding.right);
    const yScale = (val) => padding.top + (height - padding.top - padding.bottom) - ((val - minVal) / (maxVal - minVal)) * (height - padding.top - padding.bottom);

    let path = `M ${xScale(0)} ${yScale(historyValues[0])}`;
    for (let i = 1; i < historyValues.length; i++) {
      path += ` L ${xScale(i)} ${yScale(historyValues[i])}`;
    }

    let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:${height}px;">`;
    svg += `<path d="${path}" fill="none" stroke="#10b981" stroke-width="2" />`;
    historyValues.forEach((val, i) => {
      svg += `<circle cx="${xScale(i)}" cy="${yScale(val)}" r="3" fill="#10b981" />`;
    });
    svg += `<text x="${padding.left}" y="${height - 4}" fill="#64748b" font-size="10">Rounds 1 → ${historyValues.length}</text>`;
    svg += `<text x="${width - padding.right}" y="${height - 4}" fill="#10b981" font-size="10" text-anchor="end">Loss: ${historyValues[historyValues.length - 1]}</text>`;
    svg += '</svg>';

    container.innerHTML = svg;
  }
};

window.Charts = Charts;
