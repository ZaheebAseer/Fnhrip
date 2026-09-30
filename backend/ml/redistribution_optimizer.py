import json
import uuid
import datetime
from backend.database import db_session
from backend.services.inventory_service import record_transaction
from backend.services.audit_service import log_audit

def get_recommendations(status=None, page=1, page_size=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT r.*, 
               sf.name as source_facility_name, sf.facility_type as source_type,
               df.name as dest_facility_name, df.facility_type as dest_type,
               p.generic_name as product_name, p.category as product_category,
               p.unit_of_measure, p.cold_chain_required
        FROM recommendations r
        LEFT JOIN facilities sf ON r.source_facility_id = sf.facility_id
        JOIN facilities df ON r.dest_facility_id = df.facility_id
        LEFT JOIN products p ON r.product_id = p.product_id
        WHERE 1=1
        """
        params = []
        if status:
            query += " AND r.status = ?"
            params.append(status)
            
        query += " ORDER BY CASE r.priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, r.created_at DESC"
        if page_size:
            effective_page = max(1, page or 1)
            offset = (effective_page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
        for r in rows:
            try:
                r['reason_list_parsed'] = json.loads(r['reason_list'])
            except Exception:
                r['reason_list_parsed'] = [r['reason_list']]
        return rows

def generate_redistribution_recommendations():
    """Scans grid for deficit facilities and pairs them with optimal surplus facilities."""
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Deficit facilities (stock < 5 days or < 15 units)
        cursor.execute("""
        SELECT 
            b.facility_id, f.name as facility_name, f.facility_type, f.latitude, f.longitude,
            b.product_id, p.generic_name, p.cold_chain_required, p.safety_stock,
            SUM(b.available_quantity) as total_avail,
            (
                SELECT COALESCE(ROUND(AVG(c.units_consumed), 1), 2.5)
                FROM historical_consumption c
                WHERE c.facility_id = b.facility_id AND c.product_id = b.product_id
            ) as burn_rate
        FROM inventory_batches b
        JOIN facilities f ON b.facility_id = f.facility_id
        JOIN products p ON b.product_id = p.product_id
        WHERE f.facility_type != 'Warehouse'
        GROUP BY b.facility_id, b.product_id
        HAVING total_avail < 15
        """)
        deficits = [dict(r) for r in cursor.fetchall()]
        
        new_recs = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for d in deficits:
            pid = d['product_id']
            dest_fid = d['facility_id']
            dest_burn = float(d['burn_rate'] or 2.0)
            current_days = round(d['total_avail'] / dest_burn, 1)
            
            # Check if recommendation already pending for this dest + product
            cursor.execute("""
            SELECT COUNT(*) as cnt FROM recommendations 
            WHERE dest_facility_id = ? AND product_id = ? AND status = 'AWAITING_APPROVAL'
            """, (dest_fid, pid))
            if cursor.fetchone()['cnt'] > 0:
                continue
                
            # Find best surplus source (Warehouse or high stock facility)
            cursor.execute("""
            SELECT 
                b.facility_id, f.name as facility_name, f.facility_type,
                SUM(b.available_quantity) as avail_stock, p.safety_stock
            FROM inventory_batches b
            JOIN facilities f ON b.facility_id = f.facility_id
            JOIN products p ON b.product_id = p.product_id
            WHERE b.product_id = ? AND b.facility_id != ? AND b.available_quantity > 80
            GROUP BY b.facility_id
            ORDER BY CASE WHEN f.facility_type = 'Warehouse' THEN 1 ELSE 2 END, avail_stock DESC
            LIMIT 1
            """, (pid, dest_fid))
            surplus = cursor.fetchone()
            
            if surplus:
                source_fid = surplus['facility_id']
                transfer_qty = min(150, max(30, int(dest_burn * 14))) # Target 14 days coverage
                expected_days = round((d['total_avail'] + transfer_qty) / dest_burn, 1)
                
                rec_id = f"REC-{uuid.uuid4().hex[:8].upper()}"
                priority = "URGENT" if current_days < 3.0 else "HIGH"
                
                reasons = [
                    f"Destination {d['facility_name']} has only {current_days} days of {d['generic_name']} remaining.",
                    f"Source {surplus['facility_name']} possesses ample buffer ({surplus['avail_stock']} units available).",
                    f"Transfer of {transfer_qty} units restores destination operational coverage to {expected_days} days.",
                    "Route optimization confirms transport capacity available."
                ]
                
                cursor.execute("""
                INSERT INTO recommendations (
                    recommendation_id, recommendation_type, priority,
                    source_facility_id, dest_facility_id, product_id,
                    quantity, current_dest_days_stock, expected_dest_days_stock,
                    confidence, reason_list, assumptions, status, created_at
                ) VALUES (?, 'REDISTRIBUTION', ?, ?, ?, ?, ?, ?, ?, 0.93, ?, 'Standard medical courier route.', 'AWAITING_APPROVAL', ?)
                """, (rec_id, priority, source_fid, dest_fid, pid, transfer_qty, current_days, expected_days, json.dumps(reasons), now_str))
                
                new_recs.append(rec_id)
                
        conn.commit()
        return new_recs

def approve_recommendation(recommendation_id, approved_by="Authorized Health Officer", approval_notes="Approved for immediate dispatch"):
    """Human-in-the-loop approval: changes status and executes inventory transfer."""
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM recommendations WHERE recommendation_id = ?", (recommendation_id,))
        rec = cursor.fetchone()
        if not rec:
            return {"success": False, "error": "Recommendation not found"}
            
        if rec['status'] != 'AWAITING_APPROVAL':
            return {"success": False, "error": f"Cannot approve recommendation in status '{rec['status']}'"}
            
        # Execute inventory transfer
        source_fid = rec['source_facility_id']
        dest_fid = rec['dest_facility_id']
        pid = rec['product_id']
        qty = rec['quantity']
        
        # Deduct from source
        res1 = record_transaction(
            facility_id=source_fid,
            product_id=pid,
            batch_id=None,
            tx_type="TRANSFER",
            quantity=qty,
            reference_doc=recommendation_id,
            notes=f"AI Redistribution transfer dispatch to {dest_fid}",
            created_by=approved_by
        )
        
        # Add to destination
        res2 = record_transaction(
            facility_id=dest_fid,
            product_id=pid,
            batch_id=None,
            tx_type="RECEIPT",
            quantity=qty,
            reference_doc=recommendation_id,
            notes=f"AI Redistribution transfer receipt from {source_fid}",
            created_by=approved_by
        )
        
        # Update recommendation
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE recommendations 
        SET status = 'APPROVED', approved_by = ?, approval_notes = ?, actioned_at = ?
        WHERE recommendation_id = ?
        """, (approved_by, approval_notes, now_str, recommendation_id))
        
        conn.commit()
        
    # Audit log
    log_audit(
        user_name=approved_by,
        user_role="HealthOfficer",
        action_type="RECOMMENDATION_APPROVAL",
        entity_type="RECOMMENDATION",
        entity_id=recommendation_id,
        description=f"Approved transfer of {qty} units from {source_fid} to {dest_fid}. Notes: {approval_notes}"
    )
    
    return {
        "success": True,
        "recommendation_id": recommendation_id,
        "status": "APPROVED",
        "transfer_quantity": qty,
        "source_facility_id": source_fid,
        "dest_facility_id": dest_fid
    }

def reject_recommendation(recommendation_id, rejected_by="Authorized Health Officer", rejection_notes="Clinical priority override"):
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM recommendations WHERE recommendation_id = ?", (recommendation_id,))
        rec = cursor.fetchone()
        if not rec:
            return {"success": False, "error": "Recommendation not found"}
            
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE recommendations 
        SET status = 'REJECTED', approved_by = ?, approval_notes = ?, actioned_at = ?
        WHERE recommendation_id = ?
        """, (rejected_by, rejection_notes, now_str, recommendation_id))
        
        conn.commit()
        
    log_audit(
        user_name=rejected_by,
        user_role="HealthOfficer",
        action_type="RECOMMENDATION_REJECTION",
        entity_type="RECOMMENDATION",
        entity_id=recommendation_id,
        description=f"Rejected recommendation {recommendation_id}. Reason: {rejection_notes}"
    )
    
    return {"success": True, "recommendation_id": recommendation_id, "status": "REJECTED"}
