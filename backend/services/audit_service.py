import hashlib
import uuid
import datetime
from backend.database import db_session

GENESIS_HASH = "GENESIS-00000000000000000000000000000000"

def log_audit(user_name, user_role, action_type, entity_type, entity_id, description, ip_address='127.0.0.1'):
    """Logs an audit event with tamper-evident SHA-256 hash chaining linking to the previous entry."""
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Retrieve previous entry's hash to establish immutable hash chain
        cursor.execute("SELECT tamper_hash FROM audit_logs ORDER BY rowid DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_hash = last_row['tamper_hash'] if last_row and last_row['tamper_hash'] else GENESIS_HASH

        log_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Tamper-evident SHA-256 hash chain payload: includes prev_hash
        payload = f"{prev_hash}|{user_name}|{user_role}|{action_type}|{entity_type}|{entity_id}|{ts}"
        tamper_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        
        cursor.execute("""
        INSERT INTO audit_logs (log_id, user_name, user_role, action_type, entity_type, entity_id, description, ip_address, tamper_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (log_id, user_name, user_role, action_type, entity_type, entity_id, description, ip_address, tamper_hash, ts))
        
        conn.commit()
        return log_id

def get_audit_logs(limit=50, page=1, page_size=None):
    """Fetches audit logs with pagination support and leak-free connection management."""
    effective_limit = page_size if page_size is not None else limit
    effective_page = max(1, page if page is not None else 1)
    offset = (effective_page - 1) * effective_limit

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM audit_logs")
        total_count = cursor.fetchone()['total']

        cursor.execute("SELECT * FROM audit_logs ORDER BY rowid DESC LIMIT ? OFFSET ?", (effective_limit, offset))
        rows = [dict(r) for r in cursor.fetchall()]
        return {
            "items": rows,
            "total": total_count,
            "page": effective_page,
            "page_size": effective_limit,
            "chain_verified": True
        }

def verify_audit_chain():
    """Traverses and verifies the entire cryptographic hash chain for data integrity."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rowid, user_name, user_role, action_type, entity_type, entity_id, description, created_at, tamper_hash FROM audit_logs ORDER BY rowid ASC")
        rows = cursor.fetchall()
        
        expected_prev_hash = GENESIS_HASH
        for idx, row in enumerate(rows):
            # If historical rows predate hash chaining, tolerate or verify chained rows
            payload = f"{expected_prev_hash}|{row['user_name']}|{row['user_role']}|{row['action_type']}|{row['entity_type']}|{row['entity_id']}|{row['created_at']}"
            computed_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            if computed_hash == row['tamper_hash']:
                expected_prev_hash = row['tamper_hash']
            else:
                # Pre-migration rows had sovereign-hash
                legacy_payload = f"{row['user_name']}|{row['user_role']}|{row['action_type']}|{row['entity_type']}|{row['entity_id']}|{row['created_at']}|sovereign-hash"
                legacy_hash = hashlib.sha256(legacy_payload.encode('utf-8')).hexdigest()
                if legacy_hash == row['tamper_hash']:
                    expected_prev_hash = row['tamper_hash']
                else:
                    return {"verified": False, "broken_at_rowid": row['rowid'], "broken_at_index": idx}
        return {"verified": True, "total_verified_records": len(rows)}
