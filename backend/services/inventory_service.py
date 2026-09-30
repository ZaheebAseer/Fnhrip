import datetime
import uuid
from backend.database import db_session

def get_products():
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY category, generic_name")
        products = [dict(p) for p in cursor.fetchall()]
        return products

def get_inventory_summary(facility_id=None, district_id=None, page=1, page_size=None):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            p.product_id, p.code as product_code, p.generic_name, p.brand_name,
            p.category, p.unit_of_measure, p.safety_stock, p.default_lead_time_days,
            p.cold_chain_required, p.essential_medicine,
            f.facility_id, f.name as facility_name, f.facility_type,
            d.district_id, d.name as district_name,
            COALESCE(SUM(b.quantity), 0) as total_quantity,
            COALESCE(SUM(b.reserved_quantity), 0) as reserved_quantity,
            COALESCE(SUM(b.available_quantity), 0) as available_quantity,
            (
                SELECT COALESCE(ROUND(AVG(c.units_consumed), 1), 2.5)
                FROM historical_consumption c
                WHERE c.facility_id = f.facility_id AND c.product_id = p.product_id
                AND c.record_date >= date('now', '-30 days')
            ) as avg_daily_consumption
        FROM products p
        CROSS JOIN facilities f
        JOIN districts d ON f.district_id = d.district_id
        LEFT JOIN inventory_batches b ON p.product_id = b.product_id AND f.facility_id = b.facility_id
        WHERE f.facility_type != 'Warehouse'
        """
        params = []
        if facility_id:
            query += " AND f.facility_id = ?"
            params.append(facility_id)
        if district_id:
            query += " AND d.district_id = ?"
            params.append(district_id)
            
        query += " GROUP BY p.product_id, f.facility_id ORDER BY f.district_id, f.facility_id, p.product_id"
        if page_size:
            effective_page = max(1, page or 1)
            offset = (effective_page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
        # Calculate Days of Stock, Reorder Point, and Risk Classification
        results = []
        for row in rows:
            daily_cons = row['avg_daily_consumption'] or 2.0
            avail = row['available_quantity']
            lead_time = row['default_lead_time_days']
            safety = row['safety_stock']
            
            days_of_stock = round(avail / daily_cons, 1) if daily_cons > 0 else 999.0
            reorder_point = round((lead_time * daily_cons) + safety, 0)
            
            if days_of_stock <= 5.0 or avail <= 2:
                risk_level = "CRITICAL"
                risk_class = "risk-critical"
            elif days_of_stock <= 14.0:
                risk_level = "WARNING"
                risk_class = "risk-warning"
            elif days_of_stock <= 25.0:
                risk_level = "WATCH"
                risk_class = "risk-watch"
            else:
                risk_level = "NORMAL"
                risk_class = "risk-normal"
                
            row['days_of_stock'] = days_of_stock
            row['reorder_point'] = reorder_point
            row['risk_level'] = risk_level
            row['risk_class'] = risk_class
            results.append(row)
            
        return results

def get_facility_batches(facility_id):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT b.*, p.generic_name, p.brand_name, p.category, p.unit_of_measure,
               CAST((julianday(b.expiry_date) - julianday('now')) AS INTEGER) as days_to_expiry
        FROM inventory_batches b
        JOIN products p ON b.product_id = p.product_id
        WHERE b.facility_id = ?
        ORDER BY b.expiry_date ASC -- FEFO Order
        """, (facility_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        
        for r in rows:
            dte = r['days_to_expiry']
            if dte < 0:
                r['expiry_status'] = "EXPIRED"
                r['expiry_badge'] = "badge-expired"
            elif dte <= 14:
                r['expiry_status'] = "EXPIRING_14D"
                r['expiry_badge'] = "badge-danger"
            elif dte <= 45:
                r['expiry_status'] = "EXPIRING_45D"
                r['expiry_badge'] = "badge-warning"
            else:
                r['expiry_status'] = "STABLE"
                r['expiry_badge'] = "badge-success"
                
        return rows

def get_fefo_expiries(days_threshold=45):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT b.*, p.generic_name, p.brand_name, p.category, p.unit_of_measure,
               f.name as facility_name, f.facility_type, d.name as district_name,
               CAST((julianday(b.expiry_date) - julianday('now')) AS INTEGER) as days_to_expiry
        FROM inventory_batches b
        JOIN products p ON b.product_id = p.product_id
        JOIN facilities f ON b.facility_id = f.facility_id
        JOIN districts d ON f.district_id = d.district_id
        WHERE julianday(b.expiry_date) - julianday('now') <= ?
        ORDER BY b.expiry_date ASC
        """, (days_threshold,))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows

def record_transaction(facility_id, product_id, batch_id, tx_type, quantity, reference_doc=None, notes=None, created_by='system'):
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Check current batch
        cursor.execute("SELECT * FROM inventory_batches WHERE batch_id = ?", (batch_id,))
        batch = cursor.fetchone()
        
        if not batch:
            # Find any matching batch for facility + product or create new
            cursor.execute("SELECT * FROM inventory_batches WHERE facility_id = ? AND product_id = ? ORDER BY expiry_date ASC LIMIT 1", (facility_id, product_id))
            batch = cursor.fetchone()
            
        current_qty = batch['quantity'] if batch else 0
        current_avail = batch['available_quantity'] if batch else 0
        
        if tx_type in ["DISPENSING", "ISSUE", "TRANSFER", "DAMAGE", "LOSS", "EXPIRY"]:
            if current_avail < quantity:
                return {"success": False, "error": f"Insufficient available stock: {current_avail} units available, requested {quantity}"}
            new_qty = current_qty - quantity
            new_avail = current_avail - quantity
        elif tx_type in ["RECEIPT", "RETURN"]:
            new_qty = current_qty + quantity
            new_avail = current_avail + quantity
        elif tx_type == "ADJUSTMENT":
            new_qty = quantity
            new_avail = quantity
        else:
            return {"success": False, "error": f"Unknown transaction type {tx_type}"}
            
        # Update batch
        if batch:
            b_id = batch['batch_id']
            cursor.execute("""
            UPDATE inventory_batches
            SET quantity = ?, available_quantity = ?, last_updated = CURRENT_TIMESTAMP
            WHERE batch_id = ?
            """, (new_qty, new_avail, b_id))
        else:
            b_id = f"BAT-{uuid.uuid4().hex[:8].upper()}"
            now_dt = datetime.datetime.now()
            exp_dt = (now_dt + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
            cursor.execute("""
            INSERT INTO inventory_batches (batch_id, facility_id, product_id, batch_number, quantity, reserved_quantity, available_quantity, manufacturing_date, expiry_date, storage_condition)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'Ambient')
            """, (b_id, facility_id, product_id, f"LOT-{b_id}", new_qty, new_avail, now_dt.strftime("%Y-%m-%d"), exp_dt))
            
        # Insert immutable transaction record
        tx_id = f"TX-{uuid.uuid4().hex[:10].upper()}"
        cursor.execute("""
        INSERT INTO inventory_transactions (transaction_id, facility_id, product_id, batch_id, transaction_type, quantity, balance_after, reference_doc, notes, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (tx_id, facility_id, product_id, b_id, tx_type, quantity, new_qty, reference_doc or tx_id, notes or "", created_by))
        
        conn.commit()
        
        return {
            "success": True,
            "transaction_id": tx_id,
            "batch_id": b_id,
            "transaction_type": tx_type,
            "quantity": quantity,
            "new_balance": new_qty,
            "new_available": new_avail
        }
