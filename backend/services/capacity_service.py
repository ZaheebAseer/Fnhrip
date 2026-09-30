from backend.database import db_session

def get_bed_capacities(district_id=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT b.*, f.name as facility_name, f.facility_type, f.operational_status,
                d.district_id, d.name as district_name,
                (SELECT COUNT(*) FROM workforce_attendance w WHERE w.facility_id = f.facility_id AND w.role_type = 'Nurse' AND w.present_count > 0) as active_nurses
        FROM bed_statuses b
        JOIN facilities f ON b.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE f.facility_type != 'Warehouse'
        """
        params = []
        if district_id:
            query += " AND d.district_id = ?"
            params.append(district_id)
            
        query += " ORDER BY (CAST(b.occupied_beds AS REAL) / MAX(b.functional_beds, 1)) DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
        for r in rows:
            fn = r['functional_beds'] or 1
            occ = r['occupied_beds']
            icu_tot = r['icu_beds'] or 1
            icu_occ = r['icu_occupied']
            o2_tot = r['oxygen_beds'] or 1
            o2_occ = r['oxygen_occupied']
            
            r['occupancy_rate'] = round(occ / fn * 100, 1)
            r['icu_occupancy_rate'] = round(icu_occ / icu_tot * 100, 1) if r['icu_beds'] > 0 else 0
            r['oxygen_occupancy_rate'] = round(o2_occ / o2_tot * 100, 1) if r['oxygen_beds'] > 0 else 0
            
            # Operational capacity principle from Section 12: physical capacity != operational capacity!
            # If nurse/staff availability is low, operational capacity is reduced.
            nurse_factor = 1.0 if r['active_nurses'] > 0 else 0.7
            r['operational_staffed_capacity'] = int(fn * nurse_factor)
            
            # Status rating
            if r['occupancy_rate'] >= 90.0 or (r['icu_beds'] > 0 and r['icu_occupancy_rate'] >= 90.0):
                r['pressure_status'] = "CRITICAL_SURGE"
                r['pressure_badge'] = "badge-danger"
            elif r['occupancy_rate'] >= 75.0:
                r['pressure_status'] = "HIGH_PRESSURE"
                r['pressure_badge'] = "badge-warning"
            else:
                r['pressure_status'] = "NORMAL_FLOW"
                r['pressure_badge'] = "badge-success"
                
        return rows
