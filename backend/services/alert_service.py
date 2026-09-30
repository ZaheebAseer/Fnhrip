import json
import uuid
import datetime
from backend.database import db_session

def get_alerts(severity=None, status=None, facility_id=None, district_id=None, page=1, page_size=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT a.*, f.name as facility_name, f.facility_type,
               d.district_id, d.name as district_name
        FROM alerts a
        JOIN facilities f ON a.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE 1=1
        """
        params = []
        if severity:
            query += " AND a.severity = ?"
            params.append(severity)
        if status:
            query += " AND a.status = ?"
            params.append(status)
        if facility_id:
            query += " AND a.facility_id = ?"
            params.append(facility_id)
        if district_id:
            query += " AND d.district_id = ?"
            params.append(district_id)
            
        # Sort order: EMERGENCY, CRITICAL, WARNING, WATCH, INFO
        query += """
        ORDER BY 
            CASE a.severity
                WHEN 'EMERGENCY' THEN 1
                WHEN 'CRITICAL' THEN 2
                WHEN 'WARNING' THEN 3
                WHEN 'WATCH' THEN 4
                ELSE 5
            END, a.detected_at DESC
        """
        if page_size:
            effective_page = max(1, page or 1)
            offset = (effective_page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
        for r in rows:
            if r['evidence']:
                try:
                    r['evidence_parsed'] = json.loads(r['evidence'])
                except Exception:
                    r['evidence_parsed'] = {}
            else:
                r['evidence_parsed'] = {}
        return rows

def update_alert_status(alert_id, new_status, owner=None, note=None):
    valid_statuses = ['CREATED', 'ACKNOWLEDGED', 'UNDER_REVIEW', 'ACTIONED', 'RESOLVED', 'DISMISSED']
    if new_status not in valid_statuses:
        return {"success": False, "error": f"Invalid status: {new_status}"}
        
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        alert = cursor.fetchone()
        if not alert:
            return {"success": False, "error": "Alert not found"}
            
        query = "UPDATE alerts SET status = ?, updated_at = CURRENT_TIMESTAMP"
        params = [new_status]
        if owner:
            query += ", owner = ?"
            params.append(owner)
        query += " WHERE alert_id = ?"
        params.append(alert_id)
        
        cursor.execute(query, params)
        conn.commit()
        return {"success": True, "alert_id": alert_id, "new_status": new_status}

def create_alert(severity, facility_id, resource_type, resource_name, reason, evidence_dict=None, recommended_action=None, probability=1.0):
    with db_session() as conn:
        cursor = conn.cursor()
        
        alert_id = f"ALT-{uuid.uuid4().hex[:6].upper()}"
        evidence_str = json.dumps(evidence_dict or {})
        
        cursor.execute("""
        INSERT INTO alerts (alert_id, severity, facility_id, resource_type, resource_name, detected_at, reason, evidence, probability, recommended_action, status, owner, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, 'CREATED', 'Operations Desk', datetime('now'))
        """, (alert_id, severity, facility_id, resource_type, resource_name, reason, evidence_str, probability, recommended_action))
        
        conn.commit()
        return {"success": True, "alert_id": alert_id}
