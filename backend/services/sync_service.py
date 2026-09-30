import datetime
from backend.database import db_session
from backend.services.inventory_service import record_transaction
from backend.services.workforce_service import record_attendance

def process_offline_batch(facility_id, queued_actions, client_timestamp=None):
    """Processes idempotent batch of actions queued by an offline client application."""
    results = []
    success_count = 0
    failure_count = 0
    
    with db_session() as conn:
        cursor = conn.cursor()
        # Check facility
        cursor.execute("SELECT * FROM facilities WHERE facility_id = ?", (facility_id,))
        fac = cursor.fetchone()
        if not fac:
            return {"success": False, "error": f"Facility {facility_id} not registered."}
            
        for action in queued_actions:
            action_type = action.get("type")
            action_id = action.get("action_id", "act_unknown")
            
            try:
                if action_type == "INVENTORY_TRANSACTION":
                    res = record_transaction(
                        facility_id=facility_id,
                        product_id=action.get("product_id"),
                        batch_id=action.get("batch_id"),
                        tx_type=action.get("tx_type", "DISPENSING"),
                        quantity=int(action.get("quantity", 1)),
                        reference_doc=action.get("reference_doc", f"SYNC-{action_id}"),
                        notes=f"[Offline Sync] {action.get('notes', '')}",
                        created_by=action.get("user", "offline_operator")
                    )
                    if res.get("success"):
                        success_count += 1
                        results.append({"action_id": action_id, "status": "APPLIED", "details": res})
                    else:
                        failure_count += 1
                        results.append({"action_id": action_id, "status": "FAILED", "error": res.get("error")})
                        
                elif action_type == "BED_UPDATE":
                    cursor.execute("""
                    UPDATE bed_statuses
                    SET occupied_beds = ?, icu_occupied = ?, oxygen_occupied = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE facility_id = ?
                    """, (
                        int(action.get("occupied_beds", 0)),
                        int(action.get("icu_occupied", 0)),
                        int(action.get("oxygen_occupied", 0)),
                        facility_id
                    ))
                    conn.commit()
                    success_count += 1
                    results.append({"action_id": action_id, "status": "APPLIED"})
                    
                elif action_type == "ATTENDANCE_RECORD":
                    record_attendance(
                        facility_id=facility_id,
                        role_type=action.get("role_type", "Nurse"),
                        scheduled=int(action.get("scheduled", 1)),
                        present=int(action.get("present", 1)),
                        absent=int(action.get("absent", 0)),
                        leave=int(action.get("leave", 0)),
                        shift_date=action.get("shift_date", datetime.datetime.now().strftime("%Y-%m-%d")),
                        shift_type=action.get("shift_type", "DAY")
                    )
                    success_count += 1
                    results.append({"action_id": action_id, "status": "APPLIED"})
                else:
                    results.append({"action_id": action_id, "status": "SKIPPED", "reason": f"Unknown type {action_type}"})
            except Exception as e:
                failure_count += 1
                results.append({"action_id": action_id, "status": "ERROR", "error": str(e)})
                
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE facilities 
        SET last_sync_time = ?, connectivity_status = 'ONLINE'
        WHERE facility_id = ?
        """, (now_str, facility_id))
        conn.commit()
        
        return {
            "success": True,
            "facility_id": facility_id,
            "processed_at": now_str,
            "total_queued": len(queued_actions),
            "applied": success_count,
            "failed": failure_count,
            "action_results": results
        }
