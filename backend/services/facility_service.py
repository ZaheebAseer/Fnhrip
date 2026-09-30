from backend.database import db_session

def get_hierarchy():
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM regions")
        regions = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM districts")
        districts = [dict(d) for d in cursor.fetchall()]
        
        cursor.execute("""
        SELECT f.*, b.total_beds, b.occupied_beds, b.icu_beds, b.icu_occupied
        FROM facilities f
        LEFT JOIN bed_statuses b ON f.facility_id = b.facility_id
        """)
        facilities = [dict(f) for f in cursor.fetchall()]
        
        # Nesting hierarchy
        district_map = {d['district_id']: {**d, 'facilities': []} for d in districts}
        for f in facilities:
            did = f['district_id']
            if did in district_map:
                district_map[did]['facilities'].append(f)
                
        region_map = {r['region_id']: {**r, 'districts': []} for r in regions}
        for d in district_map.values():
            rid = d['region_id']
            if rid in region_map:
                region_map[rid]['districts'].append(d)
                
        return list(region_map.values())

def get_facilities(district_id=None, facility_type=None, status=None, page=1, page_size=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT f.*, d.name as district_name, r.name as region_name,
               b.total_beds, b.occupied_beds, b.icu_beds, b.icu_occupied,
               b.oxygen_beds, b.oxygen_occupied, b.ambulances_available,
               (SELECT COUNT(*) FROM alerts a WHERE a.facility_id = f.facility_id AND a.status IN ('CREATED', 'UNDER_REVIEW')) as active_alerts_count
        FROM facilities f
        JOIN districts d ON f.district_id = d.district_id
        JOIN regions r ON d.region_id = r.region_id
        LEFT JOIN bed_statuses b ON f.facility_id = b.facility_id
        WHERE 1=1
        """
        params = []
        if district_id:
            query += " AND f.district_id = ?"
            params.append(district_id)
        if facility_type:
            query += " AND f.facility_type = ?"
            params.append(facility_type)
        if status:
            query += " AND f.operational_status = ?"
            params.append(status)
            
        query += " ORDER BY f.district_id, f.facility_type, f.name"
        if page_size:
            effective_page = max(1, page or 1)
            offset = (effective_page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows

def get_facility_detail(facility_id):
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT f.*, d.name as district_name, r.name as region_name
        FROM facilities f
        JOIN districts d ON f.district_id = d.district_id
        JOIN regions r ON d.region_id = r.region_id
        WHERE f.facility_id = ?
        """, (facility_id,))
        fac = cursor.fetchone()
        if not fac:
            return None
            
        result = dict(fac)
        
        # Beds
        cursor.execute("SELECT * FROM bed_statuses WHERE facility_id = ?", (facility_id,))
        bed = cursor.fetchone()
        result['bed_status'] = dict(bed) if bed else None
        
        # Workforce
        cursor.execute("SELECT * FROM workforce_attendance WHERE facility_id = ?", (facility_id,))
        result['workforce'] = [dict(r) for r in cursor.fetchall()]
        
        # Active alerts
        cursor.execute("SELECT * FROM alerts WHERE facility_id = ? AND status != 'RESOLVED' ORDER BY detected_at DESC", (facility_id,))
        result['alerts'] = [dict(r) for r in cursor.fetchall()]
        
        return result

def get_national_metrics():
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Total facilities and reporting count
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN connectivity_status != 'OFFLINE' THEN 1 ELSE 0 END) as online FROM facilities")
        fac_counts = cursor.fetchone()
        
        # Beds total & occupied
        cursor.execute("""
        SELECT 
            SUM(total_beds) as total_beds,
            SUM(functional_beds) as functional_beds,
            SUM(occupied_beds) as occupied_beds,
            SUM(icu_beds) as icu_beds,
            SUM(icu_occupied) as icu_occupied,
            SUM(oxygen_beds) as oxygen_beds,
            SUM(oxygen_occupied) as oxygen_occupied,
            SUM(ambulances_total) as ambulances_total,
            SUM(ambulances_available) as ambulances_available
        FROM bed_statuses
        """)
        bed_counts = dict(cursor.fetchone())
        
        # Workforce coverage
        cursor.execute("""
        SELECT 
            SUM(scheduled_count) as scheduled,
            SUM(present_count) as present,
            SUM(absent_count) as absent
        FROM workforce_attendance
        """)
        wf = dict(cursor.fetchone())
        wf_coverage = round((wf['present'] / wf['scheduled'] * 100) if wf['scheduled'] else 100.0, 1)
        
        # Alerts count by severity
        cursor.execute("""
        SELECT 
            COUNT(*) as total_alerts,
            SUM(CASE WHEN severity = 'EMERGENCY' THEN 1 ELSE 0 END) as emergency_alerts,
            SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) as critical_alerts,
            SUM(CASE WHEN severity = 'WARNING' THEN 1 ELSE 0 END) as warning_alerts
        FROM alerts WHERE status NOT IN ('RESOLVED', 'DISMISSED')
        """)
        alert_summary = dict(cursor.fetchone())
        
        # Pending AI recommendations
        cursor.execute("SELECT COUNT(*) as pending_recs FROM recommendations WHERE status = 'AWAITING_APPROVAL'")
        pending_recs = cursor.fetchone()['pending_recs']
        
        # Average data quality
        cursor.execute("SELECT AVG(data_quality_score) as avg_dq FROM facilities")
        avg_dq = round(cursor.fetchone()['avg_dq'] or 90.0, 1)
        
        # Stockout risk counts across facilities
        cursor.execute("""
        SELECT COUNT(DISTINCT facility_id || '-' || product_id) as low_stock_items
        FROM inventory_batches
        WHERE available_quantity < 15
        """)
        low_stock = cursor.fetchone()['low_stock_items']
        
        # Near expiry items (within 30 days)
        cursor.execute("""
        SELECT COUNT(*) as near_expiry_count
        FROM inventory_batches
        WHERE expiry_date <= date('now', '+30 days')
        """)
        near_expiry = cursor.fetchone()['near_expiry_count']
        
        total_beds = bed_counts.get('total_beds') or 1
        occ_beds = bed_counts.get('occupied_beds') or 0
        icu_total = bed_counts.get('icu_beds') or 1
        icu_occ = bed_counts.get('icu_occupied') or 0
        
        return {
            "facilities_reporting": fac_counts['online'],
            "facilities_total": fac_counts['total'],
            "facilities_offline": fac_counts['total'] - fac_counts['online'],
            "bed_occupancy_rate": round(occ_beds / total_beds * 100, 1) if total_beds > 0 else 0,
            "total_beds": total_beds,
            "occupied_beds": occ_beds,
            "available_beds": total_beds - occ_beds,
            "icu_occupancy_rate": round(icu_occ / icu_total * 100, 1) if icu_total > 0 else 0,
            "icu_beds": icu_total,
            "icu_occupied": icu_occ,
            "workforce_coverage_pct": wf_coverage,
            "staff_scheduled": wf['scheduled'],
            "staff_present": wf['present'],
            "staff_absent": wf['absent'],
            "critical_alerts": alert_summary['critical_alerts'],
            "emergency_alerts": alert_summary['emergency_alerts'],
            "active_alerts_total": alert_summary['total_alerts'],
            "pending_recommendations": pending_recs,
            "critical_stockouts_count": low_stock,
            "batches_near_expiry": near_expiry,
            "national_data_quality_score": avg_dq
        }
