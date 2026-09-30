import sqlite3
import os
from backend.config import DATABASE_PATH

from contextlib import contextmanager

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_session():
    """Context manager for database connections ensuring leak-free cleanup."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

def init_db(schema_sql=None):
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Create tables if not exists
        cursor.executescript('''
        CREATE TABLE IF NOT EXISTS regions (
            region_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS districts (
            district_id TEXT PRIMARY KEY,
            region_id TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            population INTEGER NOT NULL,
            FOREIGN KEY (region_id) REFERENCES regions (region_id)
        );

        CREATE TABLE IF NOT EXISTS facilities (
            facility_id TEXT PRIMARY KEY,
            district_id TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            facility_type TEXT NOT NULL, -- PHC, CHC, District Hospital, Medical College, Warehouse
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            catchment_population INTEGER NOT NULL,
            operational_status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, DEGRADED, OFFLINE
            storage_capacity_sqft REAL NOT NULL,
            cold_chain_capacity_liters REAL NOT NULL,
            total_beds INTEGER NOT NULL DEFAULT 0,
            connectivity_status TEXT NOT NULL DEFAULT 'ONLINE', -- ONLINE, INTERMITTENT, OFFLINE
            electricity_status TEXT NOT NULL DEFAULT 'GRID_STABLE', -- GRID_STABLE, SOLAR_BACKUP, GENERATOR_ONLY
            data_quality_score REAL NOT NULL DEFAULT 90.0,
            last_sync_time TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (district_id) REFERENCES districts (district_id)
        );

        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            generic_name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            category TEXT NOT NULL, -- Antibiotics, Antidiabetics, Analgesics, Vaccines, Emergency, Diagnostics
            therapeutic_class TEXT NOT NULL,
            strength TEXT NOT NULL,
            dosage_form TEXT NOT NULL,
            unit_of_measure TEXT NOT NULL,
            pack_size INTEGER NOT NULL DEFAULT 1,
            essential_medicine INTEGER NOT NULL DEFAULT 1,
            cold_chain_required INTEGER NOT NULL DEFAULT 0,
            controlled_item INTEGER NOT NULL DEFAULT 0,
            minimum_stock INTEGER NOT NULL,
            maximum_stock INTEGER NOT NULL,
            safety_stock INTEGER NOT NULL,
            default_lead_time_days INTEGER NOT NULL,
            unit_price REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory_batches (
            batch_id TEXT PRIMARY KEY,
            facility_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reserved_quantity INTEGER NOT NULL DEFAULT 0,
            available_quantity INTEGER NOT NULL,
            manufacturing_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            storage_condition TEXT NOT NULL, -- Ambient, Cold Chain (2-8C), Frozen (-20C)
            last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );

        CREATE TABLE IF NOT EXISTS inventory_transactions (
            transaction_id TEXT PRIMARY KEY,
            facility_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            batch_id TEXT,
            transaction_type TEXT NOT NULL, -- RECEIPT, DISPENSING, ISSUE, TRANSFER, ADJUSTMENT, LOSS, DAMAGE, EXPIRY
            quantity INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            reference_doc TEXT,
            notes TEXT,
            created_by TEXT NOT NULL DEFAULT 'system',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );

        CREATE TABLE IF NOT EXISTS bed_statuses (
            facility_id TEXT PRIMARY KEY,
            total_beds INTEGER NOT NULL,
            functional_beds INTEGER NOT NULL,
            occupied_beds INTEGER NOT NULL,
            available_beds INTEGER NOT NULL,
            icu_beds INTEGER NOT NULL DEFAULT 0,
            icu_occupied INTEGER NOT NULL DEFAULT 0,
            oxygen_beds INTEGER NOT NULL DEFAULT 0,
            oxygen_occupied INTEGER NOT NULL DEFAULT 0,
            isolation_beds INTEGER NOT NULL DEFAULT 0,
            isolation_occupied INTEGER NOT NULL DEFAULT 0,
            ventilators_total INTEGER NOT NULL DEFAULT 0,
            ventilators_in_use INTEGER NOT NULL DEFAULT 0,
            ambulances_total INTEGER NOT NULL DEFAULT 0,
            ambulances_available INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id)
        );

        CREATE TABLE IF NOT EXISTS workforce_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT NOT NULL,
            role_type TEXT NOT NULL, -- Doctor, Nurse, Pharmacist, Lab Technician, Paramedic, Admin
            scheduled_count INTEGER NOT NULL,
            present_count INTEGER NOT NULL,
            absent_count INTEGER NOT NULL,
            leave_count INTEGER NOT NULL,
            deployed_elsewhere INTEGER NOT NULL DEFAULT 0,
            shift_date TEXT NOT NULL,
            shift_type TEXT NOT NULL DEFAULT 'DAY',
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            alert_id TEXT PRIMARY KEY,
            severity TEXT NOT NULL, -- INFO, WATCH, WARNING, CRITICAL, EMERGENCY
            facility_id TEXT NOT NULL,
            district_id TEXT,
            resource_type TEXT NOT NULL, -- MEDICINE, BED, ICU, OXYGEN, WORKFORCE, EPIDEMIC
            resource_name TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            evidence TEXT,
            probability REAL DEFAULT 1.0,
            recommended_action TEXT,
            status TEXT NOT NULL DEFAULT 'CREATED', -- CREATED, ACKNOWLEDGED, UNDER_REVIEW, ACTIONED, RESOLVED, DISMISSED
            owner TEXT DEFAULT 'Operations Desk',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id TEXT PRIMARY KEY,
            recommendation_type TEXT NOT NULL, -- REDISTRIBUTION, PROCUREMENT, EMERGENCY_STOCK, STAFF_DEPLOY
            priority TEXT NOT NULL, -- LOW, MEDIUM, HIGH, URGENT
            source_facility_id TEXT,
            dest_facility_id TEXT NOT NULL,
            product_id TEXT,
            quantity INTEGER NOT NULL,
            current_dest_days_stock REAL,
            expected_dest_days_stock REAL,
            confidence REAL NOT NULL,
            reason_list TEXT NOT NULL, -- JSON array string
            assumptions TEXT,
            status TEXT NOT NULL DEFAULT 'AWAITING_APPROVAL', -- AWAITING_APPROVAL, APPROVED, REJECTED, EXECUTED
            approved_by TEXT,
            approval_notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actioned_at TEXT,
            FOREIGN KEY (source_facility_id) REFERENCES facilities (facility_id),
            FOREIGN KEY (dest_facility_id) REFERENCES facilities (facility_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );

        CREATE TABLE IF NOT EXISTS historical_consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            record_date TEXT NOT NULL,
            units_consumed INTEGER NOT NULL,
            admissions_count INTEGER NOT NULL DEFAULT 0,
            outpatients_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (facility_id) REFERENCES facilities (facility_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );

        CREATE TABLE IF NOT EXISTS federated_models (
            model_id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            version TEXT NOT NULL,
            task_type TEXT NOT NULL,
            accuracy_score REAL NOT NULL,
            wape_score REAL NOT NULL,
            participating_nodes INTEGER NOT NULL,
            privacy_budget_epsilon REAL NOT NULL,
            last_aggregation_round INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'DEPLOYED_ACTIVE',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federated_nodes (
            node_id TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            node_type TEXT NOT NULL, -- National Node, Regional Gateway
            status TEXT NOT NULL DEFAULT 'ONLINE_SYNCED',
            last_round_loss REAL NOT NULL,
            samples_trained INTEGER NOT NULL,
            last_ping TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            user_role TEXT NOT NULL,
            action_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            description TEXT NOT NULL,
            ip_address TEXT DEFAULT '127.0.0.1',
            tamper_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Performance Indexes for National-Scale Operations
        CREATE INDEX IF NOT EXISTS idx_inventory_fac_prod ON inventory_batches(facility_id, product_id);
        CREATE INDEX IF NOT EXISTS idx_inventory_expiry ON inventory_batches(expiry_date);
        CREATE INDEX IF NOT EXISTS idx_transactions_facility ON inventory_transactions(facility_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_consumption_fac_prod_date ON historical_consumption(facility_id, product_id, record_date);
        CREATE INDEX IF NOT EXISTS idx_alerts_facility_status ON alerts(facility_id, status);
        CREATE INDEX IF NOT EXISTS idx_recommendations_dest_status ON recommendations(dest_facility_id, status);
        CREATE INDEX IF NOT EXISTS idx_facilities_district ON facilities(district_id);
        CREATE INDEX IF NOT EXISTS idx_workforce_fac_date ON workforce_attendance(facility_id, shift_date);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
        ''')
        conn.commit()
