from backend.database import db_session

def get_workforce_summary(facility_id=None, district_id=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT w.*, f.name as facility_name, f.facility_type,
                d.district_id, d.name as district_name
        FROM workforce_attendance w
        JOIN facilities f ON w.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE 1=1
        """
        params = []
        if facility_id:
            query += " AND w.facility_id = ?"
            params.append(facility_id)
        if district_id:
            query += " AND d.district_id = ?"
            params.append(district_id)
            
        query += " ORDER BY f.district_id, f.name, w.role_type"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
        for r in rows:
            sched = r['scheduled_count'] or 1
            pres = r['present_count']
            r['coverage_rate'] = round(pres / sched * 100, 1)
            r['shortage_headcount'] = max(0, sched - pres)
            
            if r['coverage_rate'] < 50.0:
                r['shortage_severity'] = "CRITICAL_SHORTAGE"
                r['badge_class'] = "badge-danger"
            elif r['coverage_rate'] < 80.0:
                r['shortage_severity'] = "MODERATE_SHORTAGE"
                r['badge_class'] = "badge-warning"
            else:
                r['shortage_severity'] = "OPTIMAL_STAFFING"
                r['badge_class'] = "badge-success"
                
        return rows

def record_attendance(facility_id, role_type, scheduled, present, absent, leave, shift_date, shift_type='DAY'):
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Check if record already exists for date + shift
        cursor.execute("""
        SELECT id FROM workforce_attendance 
        WHERE facility_id = ? AND role_type = ? AND shift_date = ? AND shift_type = ?
        """, (facility_id, role_type, shift_date, shift_type))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
            UPDATE workforce_attendance
            SET scheduled_count = ?, present_count = ?, absent_count = ?, leave_count = ?
            WHERE id = ?
            """, (scheduled, present, absent, leave, existing['id']))
        else:
            cursor.execute("""
            INSERT INTO workforce_attendance (facility_id, role_type, scheduled_count, present_count, absent_count, leave_count, deployed_elsewhere, shift_date, shift_type)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (facility_id, role_type, scheduled, present, absent, leave, shift_date, shift_type))
            
        conn.commit()
        return {"success": True}
