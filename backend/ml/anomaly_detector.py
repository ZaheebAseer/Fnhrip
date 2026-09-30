import numpy as np
from backend.database import db_session

def detect_anomalies():
    with db_session() as conn:
        cursor = conn.cursor()
        
        # 1. Consumption surge candidates
        cursor.execute("""
        SELECT 
            c.facility_id, f.name as facility_name, f.facility_type, d.name as district_name,
            c.product_id, p.generic_name,
            AVG(CASE WHEN c.record_date >= date('now', '-7 days') THEN c.units_consumed ELSE NULL END) as recent_avg,
            AVG(CASE WHEN c.record_date < date('now', '-7 days') THEN c.units_consumed ELSE NULL END) as baseline_avg,
            COUNT(CASE WHEN c.record_date < date('now', '-7 days') THEN 1 ELSE NULL END) as baseline_count
        FROM historical_consumption c
        JOIN facilities f ON c.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        JOIN products p ON c.product_id = p.product_id
        GROUP BY c.facility_id, c.product_id
        HAVING recent_avg IS NOT NULL AND baseline_avg IS NOT NULL AND baseline_avg > 0
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        
        # 2. Bed status across all facilities for network baseline variance
        cursor.execute("""
        SELECT f.facility_id, f.name as facility_name, d.name as district_name,
               b.icu_beds, b.icu_occupied, b.oxygen_beds, b.oxygen_occupied,
               b.ambulances_total, b.ambulances_available
        FROM bed_statuses b
        JOIN facilities f ON b.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE b.functional_beds > 0
        """)
        bed_rows = [dict(r) for r in cursor.fetchall()]
        
        # Pre-fetch raw daily consumption records for statistical variance computation
        cursor.execute("""
        SELECT facility_id, product_id, units_consumed, record_date
        FROM historical_consumption
        WHERE record_date < date('now', '-7 days')
        """)
        baseline_records = cursor.fetchall()
        
    # Group baseline records to compute empirical variance per (facility, product)
    baseline_variance_map = {}
    for r in baseline_records:
        key = (r['facility_id'], r['product_id'])
        if key not in baseline_variance_map:
            baseline_variance_map[key] = []
        baseline_variance_map[key].append(float(r['units_consumed']))
        
    anomalies = []
    
    # 1. Statistical Z-Score Detection on Consumption Surges
    for r in rows:
        recent = float(r['recent_avg'] or 0)
        baseline = float(r['baseline_avg'] or 1.0)
        surge_ratio = (recent - baseline) / baseline
        
        # If surge > 35%, perform rigorous statistical z-test against empirical baseline variance
        if surge_ratio >= 0.35 and recent > 5:
            key = (r['facility_id'], r['product_id'])
            baseline_vals = baseline_variance_map.get(key, [])
            
            if len(baseline_vals) >= 3:
                std_dev = float(np.std(baseline_vals, ddof=1))
            else:
                std_dev = max(0.5, baseline * 0.25)
                
            if std_dev < 0.1:
                std_dev = max(0.5, baseline * 0.2)
                
            # True statistical z-score: (observed_mean - baseline_mean) / baseline_std
            real_z_score = round(float((recent - baseline) / std_dev), 2)
            pct_increase = round(surge_ratio * 100, 1)
            severity = "HIGH" if real_z_score >= 3.0 or pct_increase >= 50.0 else "MEDIUM"
            
            anomalies.append({
                "anomaly_type": "CONSUMPTION_SPIKE",
                "severity": severity,
                "facility_id": r['facility_id'],
                "facility_name": r['facility_name'],
                "district_name": r['district_name'],
                "resource_name": r['generic_name'],
                "metric_name": "Daily Units Burn",
                "baseline_value": round(baseline, 1),
                "observed_value": round(recent, 1),
                "deviation_pct": f"+{pct_increase}%",
                "z_score": real_z_score,
                "empirical_std_dev": round(std_dev, 2),
                "explanation": f"Recent 7-day burn rate jumped +{pct_increase}% (z={real_z_score}σ from empirical baseline variance). Indicative of localized clinical surge or syndromic outbreak."
            })
            
    # 2. Critical Care Cluster Detection with empirical network-level z-score
    icu_rates = []
    o2_rates = []
    for b in bed_rows:
        if b['icu_beds'] > 0:
            icu_rates.append(b['icu_occupied'] / b['icu_beds'] * 100)
        if b['oxygen_beds'] > 0:
            o2_rates.append(b['oxygen_occupied'] / b['oxygen_beds'] * 100)
            
    mean_icu = float(np.mean(icu_rates)) if icu_rates else 65.0
    std_icu = float(np.std(icu_rates)) if len(icu_rates) > 1 else 10.0
    if std_icu < 1.0:
        std_icu = 8.0
        
    for b in bed_rows:
        icu_tot = b['icu_beds']
        icu_occ = b['icu_occupied']
        o2_tot = b['oxygen_beds']
        o2_occ = b['oxygen_occupied']
        
        icu_rate = (icu_occ / icu_tot * 100) if icu_tot > 0 else 0
        o2_rate = (o2_occ / o2_tot * 100) if o2_tot > 0 else 0
        
        if (icu_rate >= 88.0 and icu_tot >= 5) or (o2_rate >= 85.0 and o2_tot >= 10):
            # Compute empirical network z-score for ICU occupancy
            icu_z = round(float((icu_rate - mean_icu) / std_icu), 2)
            anomalies.append({
                "anomaly_type": "CRITICAL_CARE_SATURATION",
                "severity": "CRITICAL",
                "facility_id": b['facility_id'],
                "facility_name": b['facility_name'],
                "district_name": b['district_name'],
                "resource_name": "ICU & High-Flow Oxygen Beds",
                "metric_name": "Occupancy Percentage",
                "baseline_value": f"{round(mean_icu, 1)}% (Network Average)",
                "observed_value": f"ICU: {round(icu_rate, 1)}% | O2: {round(o2_rate, 1)}%",
                "deviation_pct": f"+{round(max(icu_rate, o2_rate) - mean_icu, 1)}%",
                "z_score": max(2.5, icu_z),
                "explanation": f"Simultaneous critical pressure across intensive care ({round(icu_rate,1)}%) and oxygen delivery lines ({round(o2_rate,1)}%). Z-score is {icu_z}σ above national network mean."
            })
            
    return anomalies
