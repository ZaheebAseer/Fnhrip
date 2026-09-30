import hashlib
import json
import random
import datetime
from backend.database import get_db, db_session, init_db
from backend.services.audit_service import log_audit

def seed_database(force=False):
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if already seeded
    cursor.execute("SELECT count(*) as cnt FROM facilities")
    if cursor.fetchone()['cnt'] > 0 and not force:
        conn.close()
        return
        
    if force:
        cursor.executescript("""
        DELETE FROM audit_logs;
        DELETE FROM federated_nodes;
        DELETE FROM federated_models;
        DELETE FROM historical_consumption;
        DELETE FROM recommendations;
        DELETE FROM alerts;
        DELETE FROM workforce_attendance;
        DELETE FROM bed_statuses;
        DELETE FROM inventory_transactions;
        DELETE FROM inventory_batches;
        DELETE FROM products;
        DELETE FROM facilities;
        DELETE FROM districts;
        DELETE FROM regions;
        """)
    
    print("Seeding FNHRIP operational database with realistic national health grid dataset...")
    
    # 1. Regions
    regions = [
        ("REG-01", "Capital Health Region", "CHR", "Metropolitan administrative zone with tertiary healthcare centers"),
        ("REG-02", "Northern Highlands Zone", "NHZ", "Hilly district network with dispersed rural PHCs"),
        ("REG-03", "Coastal River Delta", "CRD", "High-density maritime riverine community corridor")
    ]
    cursor.executemany("INSERT INTO regions VALUES (?, ?, ?, ?)", regions)

    # 2. Districts
    districts = [
        ("DST-01", "REG-01", "Metro Central District", "MCD", 1850000),
        ("DST-02", "REG-01", "North Suburb District", "NSD", 920000),
        ("DST-03", "REG-02", "Highland Green District", "HGD", 540000),
        ("DST-04", "REG-02", "Valley Springs District", "VSD", 410000),
        ("DST-05", "REG-03", "Coastal Bay District", "CBD", 1120000),
        ("DST-06", "REG-03", "River Delta District", "RDD", 680000)
    ]
    cursor.executemany("INSERT INTO districts VALUES (?, ?, ?, ?, ?)", districts)

    # 3. Facilities (20+ diverse facilities)
    facilities_data = [
        # Metro Central (Tier 3 & Warehouses)
        ("FAC-001", "DST-01", "Central State Medical College & Hospital", "CSMCH", "Medical College", 28.6139, 77.2090, 750000, "ACTIVE", 4500.0, 1200.0, 650, "ONLINE", "GRID_STABLE", 98.2),
        ("FAC-002", "DST-01", "National Emergency Medical Depot #1", "NEMD-1", "Warehouse", 28.6250, 77.2200, 1850000, "ACTIVE", 22000.0, 8500.0, 0, "ONLINE", "GRID_STABLE", 99.5),
        ("FAC-003", "DST-01", "Metro Civil District Hospital", "MCDH", "District Hospital", 28.6010, 77.1950, 420000, "ACTIVE", 2800.0, 650.0, 280, "ONLINE", "GRID_STABLE", 95.8),
        ("FAC-004", "DST-01", "Urban Primary Health Centre - Old City", "UPHC-OC", "PHC", 28.6350, 77.2350, 48000, "ACTIVE", 400.0, 80.0, 12, "ONLINE", "GRID_STABLE", 92.4),
        
        # North Suburb
        ("FAC-005", "DST-02", "Suburban Sub-Divisional Hospital", "SSDH", "District Hospital", 28.7100, 77.1800, 310000, "ACTIVE", 1800.0, 450.0, 160, "ONLINE", "GRID_STABLE", 94.0),
        ("FAC-006", "DST-02", "North Community Health Centre - Sector 9", "CHC-S9", "CHC", 28.7450, 77.1550, 95000, "ACTIVE", 750.0, 140.0, 35, "ONLINE", "GRID_STABLE", 91.5),
        ("FAC-007", "DST-02", "Primary Health Centre - Riverbend", "PHC-RB", "PHC", 28.7800, 77.1400, 32000, "ACTIVE", 350.0, 60.0, 8, "ONLINE", "SOLAR_BACKUP", 88.6),
        
        # Highland Green
        ("FAC-008", "DST-03", "Highland District Civil Hospital", "HDCH", "District Hospital", 30.3165, 78.0322, 220000, "ACTIVE", 1500.0, 320.0, 120, "ONLINE", "GRID_STABLE", 93.2),
        ("FAC-009", "DST-03", "Mountain Ridge CHC", "CHC-MR", "CHC", 30.3800, 78.1100, 65000, "ACTIVE", 600.0, 120.0, 24, "ONLINE", "SOLAR_BACKUP", 89.0),
        ("FAC-010", "DST-03", "Highland Rural PHC - Pine Valley", "PHC-PV", "PHC", 30.4500, 78.1900, 18000, "ACTIVE", 250.0, 45.0, 6, "INTERMITTENT", "SOLAR_BACKUP", 84.5),
        ("FAC-011", "DST-03", "Highland PHC - Glacier Point", "PHC-GP", "PHC", 30.5200, 78.2500, 12000, "DEGRADED", 200.0, 30.0, 6, "OFFLINE", "GENERATOR_ONLY", 78.0),
        
        # Valley Springs
        ("FAC-012", "DST-04", "Valley Springs Base Hospital", "VSBH", "District Hospital", 29.9457, 78.1642, 190000, "ACTIVE", 1600.0, 380.0, 140, "ONLINE", "GRID_STABLE", 94.7),
        ("FAC-013", "DST-04", "Valley CHC - Orchard Gate", "CHC-OG", "CHC", 29.9800, 78.2200, 58000, "ACTIVE", 620.0, 110.0, 25, "ONLINE", "SOLAR_BACKUP", 91.0),
        ("FAC-014", "DST-04", "Valley Springs PHC - Meadow", "PHC-MD", "PHC", 30.0400, 78.2900, 22000, "ACTIVE", 300.0, 50.0, 8, "ONLINE", "GRID_STABLE", 89.4),
        
        # Coastal Bay
        ("FAC-015", "DST-05", "Coastal General Tertiary Hospital", "CGTH", "Medical College", 18.9220, 72.8347, 680000, "ACTIVE", 3800.0, 950.0, 520, "ONLINE", "GRID_STABLE", 97.5),
        ("FAC-016", "DST-05", "Port Medical Logistics Depot", "PMLD", "Warehouse", 18.9400, 72.8550, 1120000, "ACTIVE", 16500.0, 6200.0, 0, "ONLINE", "GRID_STABLE", 99.1),
        ("FAC-017", "DST-05", "Fishermen Colony CHC", "CHC-FC", "CHC", 18.8950, 72.8100, 82000, "ACTIVE", 700.0, 130.0, 30, "ONLINE", "GRID_STABLE", 92.1),
        ("FAC-018", "DST-05", "Harbor PHC - South Pier", "PHC-SP", "PHC", 18.8700, 72.8250, 26000, "ACTIVE", 320.0, 55.0, 10, "ONLINE", "GRID_STABLE", 90.8),
        
        # River Delta
        ("FAC-019", "DST-06", "Delta Memorial Hospital", "DMH", "District Hospital", 19.0760, 72.8777, 340000, "ACTIVE", 2200.0, 520.0, 210, "ONLINE", "GRID_STABLE", 95.0),
        ("FAC-020", "DST-06", "Delta Island CHC - Mangrove", "CHC-MG", "CHC", 19.1200, 72.9300, 72000, "ACTIVE", 650.0, 100.0, 26, "INTERMITTENT", "SOLAR_BACKUP", 86.2),
        ("FAC-021", "DST-06", "River Delta PHC - Estuary", "PHC-ES", "PHC", 19.1600, 72.9800, 29000, "ACTIVE", 280.0, 40.0, 8, "ONLINE", "GRID_STABLE", 88.0)
    ]
    cursor.executemany("""
    INSERT INTO facilities (facility_id, district_id, name, code, facility_type, latitude, longitude, catchment_population, operational_status, storage_capacity_sqft, cold_chain_capacity_liters, total_beds, connectivity_status, electricity_status, data_quality_score, last_sync_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, facilities_data)

    # 4. Products Master (Essential Medicines, Vaccines, Diagnostics, Oxygen)
    products_data = [
        ("MED-001", "INS-REG-100", "Insulin Regular (Human)", "Huminsulin R", "Antidiabetics", "Hormones", "100 IU/ml", "Vial 10ml", "Vial", 1, 1, 1, 0, 80, 800, 150, 5, 12.50),
        ("MED-002", "AMX-CLV-625", "Amoxicillin + Clavulanic Acid", "Augmentin", "Antibiotics", "Penicillins", "625 mg", "Tablet", "Strip of 10", 10, 1, 0, 0, 200, 2500, 400, 7, 3.20),
        ("MED-003", "CEF-TRI-1G", "Ceftriaxone Sodium Injection", "Rocephin", "Antibiotics", "Cephalosporins", "1 g", "Vial", "Vial", 1, 1, 0, 0, 150, 1800, 300, 6, 2.80),
        ("MED-004", "ART-LUM-TAB", "Artemether + Lumefantrine", "Coartem", "Antimalarials", "Artemisinin Comb.", "20/120 mg", "Tablet", "Pack of 24", 24, 1, 0, 0, 100, 1200, 200, 10, 4.50),
        ("MED-005", "OXY-TOC-10", "Oxytocin Injection", "Pitocin", "Emergency Maternal", "Uterotonics", "10 IU/ml", "Ampoule 1ml", "Ampoule", 1, 1, 1, 0, 120, 1400, 250, 4, 1.10),
        ("MED-006", "SAL-IV-500", "Normal Saline (0.9% NaCl)", "NS Infusion", "Intravenous Fluids", "Electrolytes", "0.9%", "Bottle 500ml", "Bottle", 1, 1, 0, 0, 400, 5000, 800, 3, 0.75),
        ("MED-007", "DEX-IV-500", "Dextrose 5% Solution", "D5 Infusion", "Intravenous Fluids", "Carbohydrates", "5%", "Bottle 500ml", "Bottle", 1, 1, 0, 0, 300, 3500, 600, 3, 0.85),
        ("MED-008", "MED-OXY-CYL", "Medical Oxygen Compressed", "Med-O2 Bulk", "Respiratory Gas", "Medical Gases", "Bulk 47L D-Cyl", "Cylinder", "Cylinder", 1, 1, 0, 0, 25, 250, 50, 2, 28.00),
        ("MED-009", "DTP-VAC-05", "Pentavalent DTP-HepB-Hib Vaccine", "Pentavac", "Vaccines", "Immunoglobulins", "0.5 ml/dose", "10-Dose Vial", "Vial", 10, 1, 1, 0, 60, 650, 120, 14, 18.00),
        ("MED-010", "RAB-IG-SER", "Rabies Immunoglobulin (Human)", "KamRAB", "Emergency Antidotes", "Sera", "150 IU/ml", "Vial 2ml", "Vial", 1, 1, 1, 0, 20, 180, 40, 12, 45.00),
        ("MED-011", "PAR-INF-1G", "Paracetamol IV Infusion", "Perfalgan", "Analgesics/Antipyretic", "Anilides", "10 mg/ml", "Bottle 100ml", "Bottle", 1, 1, 0, 0, 150, 2200, 350, 4, 1.90),
        ("MED-012", "SAL-INH-100", "Salbutamol Inhaler (CFC-free)", "Ventolin", "Respiratory", "Beta-2 Agonists", "100 mcg/act", "Canister 200d", "Inhaler", 1, 1, 0, 0, 80, 950, 160, 7, 5.40),
        ("MED-013", "EPI-INJ-1MG", "Epinephrine (Adrenaline) 1:1000", "Adrenalin", "Emergency Resuscitation", "Adrenergics", "1 mg/ml", "Ampoule 1ml", "Ampoule", 1, 1, 1, 1, 50, 400, 100, 3, 2.20),
        ("MED-014", "MET-TAB-500", "Metformin Hydrochloride", "Glucophage", "Antidiabetics", "Biguanides", "500 mg", "Tablet", "Strip of 20", 20, 1, 0, 0, 300, 4000, 600, 8, 1.40),
        ("MED-015", "PPE-KIT-L3", "Full Biohazard Level-3 PPE Kit", "SafeShield Pro", "Infection Control", "Personal Protection", "Complete Set", "Kit", "Kit", 1, 1, 0, 0, 100, 1500, 250, 5, 8.50)
    ]
    cursor.executemany("""
    INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, products_data)

    # 5. Inventory Batches across facilities
    # To demonstrate realistic conditions:
    # - Some facilities have healthy inventory
    # - Some facilities have CRITICAL stockouts (e.g. FAC-010, FAC-011, FAC-004)
    # - Some have surplus (e.g. NEMD-1, CSMCH, PMLD)
    # - Some batches expire soon (within 14d or 28d) to show FEFO alerting
    now = datetime.datetime.now()
    batch_counter = 100
    
    batches = []
    transactions = []
    
    for fac in facilities_data:
        fac_id = fac[0]
        fac_type = fac[4]
        
        is_warehouse = fac_type == "Warehouse"
        is_tertiary = fac_type == "Medical College" or fac_type == "District Hospital"
        
        for prod in products_data:
            prod_id = prod[0]
            safety = prod[14]
            is_cold = prod[11]
            
            # Stock profile generator
            if is_warehouse:
                multiplier = 6.0
            elif is_tertiary:
                multiplier = 2.5
            else: # PHC or CHC
                multiplier = 0.8
                
            # Random variation: create simulated shortages at certain remote facilities
            if fac_id in ["FAC-010", "FAC-011"] and prod_id in ["MED-001", "MED-008", "MED-005"]:
                # Severe shortage!
                qty = random.randint(1, 12)
            elif fac_id in ["FAC-004", "FAC-007"] and prod_id in ["MED-003", "MED-013"]:
                qty = random.randint(0, 8)
            else:
                qty = int(safety * multiplier * random.uniform(0.7, 1.6))
                
            reserved = int(qty * 0.1) if qty > 10 else 0
            available = qty - reserved
            
            # Batch 1 (Primary)
            batch_counter += 1
            b_id = f"BAT-{batch_counter}"
            
            # Simulated expiry: trigger FEFO warning on some batches!
            if batch_counter % 9 == 0:
                expiry_dt = (now + datetime.timedelta(days=random.randint(7, 18))).strftime("%Y-%m-%d")
            elif batch_counter % 5 == 0:
                expiry_dt = (now + datetime.timedelta(days=random.randint(25, 45))).strftime("%Y-%m-%d")
            else:
                expiry_dt = (now + datetime.timedelta(days=random.randint(180, 520))).strftime("%Y-%m-%d")
                
            mfg_dt = (now - datetime.timedelta(days=random.randint(60, 240))).strftime("%Y-%m-%d")
            storage = "Cold Chain (2-8C)" if is_cold else "Ambient"
            
            batches.append((
                b_id, fac_id, prod_id, f"LOT-2026-{batch_counter}",
                qty, reserved, available, mfg_dt, expiry_dt, storage
            ))
            
            # Sample initial transaction
            t_id = f"TX-{batch_counter}"
            transactions.append((
                t_id, fac_id, prod_id, b_id, "RECEIPT", qty, qty,
                f"GRN-2026-{batch_counter}", "Periodic replenishment stock receipt", "sys-auto", now.strftime("%Y-%m-%d %H:%M:%S")
            ))

    cursor.executemany("""
    INSERT INTO inventory_batches (batch_id, facility_id, product_id, batch_number, quantity, reserved_quantity, available_quantity, manufacturing_date, expiry_date, storage_condition, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, batches)

    cursor.executemany("""
    INSERT INTO inventory_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transactions)

    # 6. Bed Statuses & Capacities
    bed_rows = []
    for fac in facilities_data:
        fac_id = fac[0]
        tot = fac[11]
        
        if tot == 0: # Warehouses
            bed_rows.append((fac_id, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 3))
            continue
            
        functional = int(tot * random.uniform(0.92, 0.98))
        
        # High occupancy pressure in tertiary/urban centers
        if fac[4] in ["Medical College", "District Hospital"]:
            occupancy_rate = random.uniform(0.82, 0.96)
            icu_total = max(8, int(tot * 0.14))
            icu_occ = int(icu_total * random.uniform(0.85, 0.98)) # High ICU stress!
            o2_total = max(15, int(tot * 0.35))
            o2_occ = int(o2_total * random.uniform(0.75, 0.92))
            vent_total = max(4, int(icu_total * 0.7))
            vent_use = int(vent_total * random.uniform(0.65, 0.9))
            amb_tot = random.randint(4, 12)
            amb_avail = random.randint(1, 4)
        else: # CHC / PHC
            occupancy_rate = random.uniform(0.45, 0.78)
            icu_total = 0 if fac[4] == "PHC" else random.randint(2, 4)
            icu_occ = 0 if icu_total == 0 else random.randint(1, icu_total)
            o2_total = max(2, int(tot * 0.25))
            o2_occ = int(o2_total * random.uniform(0.3, 0.7))
            vent_total = 0 if fac[4] == "PHC" else random.randint(0, 1)
            vent_use = 0
            amb_tot = random.randint(1, 2)
            amb_avail = random.randint(0, 1)
            
        occupied = min(functional, int(functional * occupancy_rate))
        available = functional - occupied
        isolation_total = max(2, int(tot * 0.08))
        isolation_occ = int(isolation_total * random.uniform(0.2, 0.6))
        
        bed_rows.append((
            fac_id, tot, functional, occupied, available,
            icu_total, icu_occ, o2_total, o2_occ,
            isolation_total, isolation_occ,
            vent_total, vent_use, amb_tot, amb_avail
        ))
        
    cursor.executemany("""
    INSERT INTO bed_statuses (facility_id, total_beds, functional_beds, occupied_beds, available_beds, icu_beds, icu_occupied, oxygen_beds, oxygen_occupied, isolation_beds, isolation_occupied, ventilators_total, ventilators_in_use, ambulances_total, ambulances_available, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, bed_rows)

    # 7. Workforce Attendance
    roles = ["Doctor", "Nurse", "Pharmacist", "Lab Technician", "Paramedic"]
    workforce_rows = []
    
    for fac in facilities_data:
        fac_id = fac[0]
        ftype = fac[4]
        
        for role in roles:
            if ftype == "Warehouse":
                sched = 2 if role in ["Pharmacist", "Paramedic"] else 0
            elif ftype == "Medical College":
                sched = 45 if role == "Doctor" else (90 if role == "Nurse" else 15)
            elif ftype == "District Hospital":
                sched = 18 if role == "Doctor" else (35 if role == "Nurse" else 8)
            elif ftype == "CHC":
                sched = 4 if role == "Doctor" else (8 if role == "Nurse" else 3)
            else: # PHC
                sched = 2 if role == "Doctor" else (4 if role == "Nurse" else 1)
                
            if sched == 0:
                continue
                
            # Simulation of occasional rural staff shortage
            if fac_id in ["FAC-010", "FAC-011", "FAC-020"] and role in ["Doctor", "Pharmacist"]:
                present = max(0, sched - random.randint(1, 2))
                absent = sched - present
                leave = 0
            else:
                leave = 1 if sched > 6 and random.random() > 0.6 else 0
                absent = 1 if sched > 8 and random.random() > 0.7 else 0
                present = max(0, sched - leave - absent)
                
            workforce_rows.append((
                fac_id, role, sched, present, absent, leave, 0, now.strftime("%Y-%m-%d"), "DAY"
            ))
            
    cursor.executemany("""
    INSERT INTO workforce_attendance (facility_id, role_type, scheduled_count, present_count, absent_count, leave_count, deployed_elsewhere, shift_date, shift_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, workforce_rows)

    # 8. Historical Consumption (45 days of daily consumption for 6 key items)
    consumption_records = []
    key_products = ["MED-001", "MED-002", "MED-003", "MED-006", "MED-008", "MED-011"]
    
    for day_offset in range(45, 0, -1):
        rec_date = (now - datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        
        for fac in facilities_data:
            fac_id = fac[0]
            ftype = fac[4]
            if ftype == "Warehouse":
                continue
                
            base_cons = 15 if ftype in ["Medical College", "District Hospital"] else 3
            
            for pid in key_products:
                # Add weekly seasonality and slight trend
                weekday_factor = 1.2 if (day_offset % 7) in [1, 2, 3] else 0.8
                random_shock = random.uniform(0.85, 1.25)
                
                # Outbreak surge simulation in Coastal region over last 10 days!
                surge = 1.5 if (fac[1] in ["DST-05", "DST-06"] and day_offset <= 10 and pid in ["MED-002", "MED-008"]) else 1.0
                
                units = int(base_cons * weekday_factor * random_shock * surge)
                admissions = int(units * 1.8)
                opd = int(units * 7.5)
                
                consumption_records.append((
                    fac_id, pid, rec_date, max(1, units), admissions, opd
                ))
                
    cursor.executemany("""
    INSERT INTO historical_consumption (facility_id, product_id, record_date, units_consumed, admissions_count, outpatients_count)
    VALUES (?, ?, ?, ?, ?, ?)
    """, consumption_records)

    # 9. Active Early Warning Alerts
    alerts_data = [
        (
            "ALT-101", "CRITICAL", "FAC-010", "DST-03", "MEDICINE", "Insulin Regular (Human)",
            (now - datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "Stockout predicted within 48 hours. Only 2.1 days of usable stock remaining.",
            json.dumps({"current_usable_stock": 7, "daily_burn_rate": 3.2, "lead_time_days": 5, "nearby_buffer_depot": "HDCH"}),
            0.94, "Execute emergency redistribution of 120 vials from Central State Medical College.",
            "CREATED", "Emergency Ops Cell"
        ),
        (
            "ALT-102", "EMERGENCY", "FAC-001", "DST-01", "ICU", "ICU & Oxygen Critical Saturation",
            (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "ICU bed occupancy has reached 96.8% with 47 of 48 ventilators actively deployed.",
            json.dumps({"icu_total": 91, "icu_occupied": 88, "oxygen_pressure_pct": 98.2, "surge_type": "Respiratory Outbreak"}),
            0.98, "Reroute incoming acute trauma admissions to Suburban Sub-Divisional Hospital (SSDH).",
            "UNDER_REVIEW", "State Clinical Director"
        ),
        (
            "ALT-103", "WARNING", "FAC-011", "DST-03", "WORKFORCE", "Medical Officer Absence",
            (now - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "Facility operating with 0 of 2 scheduled Doctors present. Clinical coverage at 0%.",
            json.dumps({"scheduled_doctors": 2, "present_doctors": 0, "emergency_teleconsult_ready": True}),
            1.0, "Deploy mobile medical relief doctor from Mountain Ridge CHC.",
            "ACKNOWLEDGED", "District Health Officer"
        ),
        (
            "ALT-104", "WATCH", "FAC-003", "DST-01", "MEDICINE", "FEFO Expiry Risk: Amoxicillin 625mg",
            (now - datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            "350 units in Batch LOT-2026-108 expiring in 14 days with current consumption rate insufficient to deplete.",
            json.dumps({"expiring_qty": 350, "days_to_expiry": 14, "forecast_facility_burn": 110, "surplus_qty": 240}),
            0.87, "Redistribute 240 units to high-consumption Metro Civil District Hospital.",
            "CREATED", "Supply Chain Pharmacist"
        ),
        (
            "ALT-105", "CRITICAL", "FAC-020", "DST-06", "OXYGEN", "Medical Oxygen Bulk D-Cylinders",
            (now - datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "Respiratory patient surge in Delta Island has depleted oxygen backup to under 3 days.",
            json.dumps({"cylinders_available": 3, "avg_daily_burn": 1.4, "boat_transit_lead_days": 2}),
            0.92, "Dispatch fast barge with 18 D-Cylinders from Port Medical Logistics Depot (PMLD).",
            "CREATED", "Coastal Emergency Unit"
        )
    ]
    cursor.executemany("""
    INSERT INTO alerts (alert_id, severity, facility_id, district_id, resource_type, resource_name, detected_at, reason, evidence, probability, recommended_action, status, owner, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, alerts_data)

    # 10. AI Redistribution Recommendations with Explainable AI Proof
    recs_data = [
        (
            "REC-2026-001", "REDISTRIBUTION", "URGENT", "FAC-002", "FAC-010", "MED-001",
            120, 2.1, 19.5, 0.96,
            json.dumps([
                "Destination facility Highland Rural PHC projected stockout in 1.8 days",
                "Source National Emergency Depot holds 3,400 surplus units (exceeds 180 days buffer)",
                "Lead time via Hill Express Route: 9.5 hours; cold chain vehicle available",
                "Destination catchment population 18,000 has no alternative cold-chain pharmacy within 25km"
            ]),
            "Cold box container temp guaranteed between 2-8 deg C during 10-hour transit. Driver scheduled.",
            "AWAITING_APPROVAL"
        ),
        (
            "REC-2026-002", "REDISTRIBUTION", "HIGH", "FAC-016", "FAC-020", "MED-008",
            18, 2.3, 14.0, 0.91,
            json.dumps([
                "Destination Delta Island CHC experiencing +45% respiratory surge",
                "Port Logistics Depot holds 180 cylinders; current depot stock coverage is 52 days",
                "Maritime courier boat transit slot available at 14:00 today",
                "No adverse weather forecast along river delta route"
            ]),
            "Cylinder hydro-test certifications valid through 2028. Secure strap transport approved.",
            "AWAITING_APPROVAL"
        ),
        (
            "REC-2026-003", "REDISTRIBUTION", "MEDIUM", "FAC-001", "FAC-004", "MED-003",
            90, 3.4, 21.0, 0.88,
            json.dumps([
                "Urban PHC Old City Ceftriaxone 1g running low due to seasonal outpatient surge",
                "Central State Hospital holds 1,120 units with fresh batch arrival scheduled tomorrow",
                "Inter-urban transfer distance: 6.2 km (approx 25 mins transit)"
            ]),
            "Standard ambient temperature transfer. Dispatch via local district supply van.",
            "AWAITING_APPROVAL"
        )
    ]
    cursor.executemany("""
    INSERT INTO recommendations (recommendation_id, recommendation_type, priority, source_facility_id, dest_facility_id, product_id, quantity, current_dest_days_stock, expected_dest_days_stock, confidence, reason_list, assumptions, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, recs_data)

    # 11. Federated Learning Models & Nodes
    models_data = [
        ("MOD-DEMAND-01", "Cross-Border Essential Medicine Demand Forecaster", "v2.4-FED", "Time-Series Regression", 0.924, 0.082, 4, 0.65, 18, "DEPLOYED_ACTIVE"),
        ("MOD-STOCKOUT-02", "Lead-Time Supply Chain Stockout Calibrator", "v1.9-FED", "Binary Hazard Model", 0.941, 0.059, 4, 0.50, 14, "DEPLOYED_ACTIVE"),
        ("MOD-OUTBREAK-03", "Early Syndromic Outbreak Cluster Classifier", "v3.1-FED", "Spatial-Temporal Anomaly", 0.898, 0.110, 3, 0.80, 22, "DEPLOYED_ACTIVE")
    ]
    cursor.executemany("""
    INSERT INTO federated_models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, models_data)

    nodes_data = [
        ("NODE-NAT-01", "Country Sovereign Node - National Grid", "National Node", "ONLINE_SYNCED", 0.042, 145000),
        ("NODE-INT-02", "Participant Node - Regional Partner Alpha", "Regional Gateway", "ONLINE_SYNCED", 0.051, 98000),
        ("NODE-INT-03", "Participant Node - Partner Delta", "Regional Gateway", "ONLINE_SYNCED", 0.048, 112000),
        ("NODE-INT-04", "Participant Node - Partner Gamma", "Regional Gateway", "ONLINE_SYNCED", 0.063, 76000)
    ]
    cursor.executemany("""
    INSERT INTO federated_nodes VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, nodes_data)

    conn.commit()
    conn.close()
    
    # 12. Audit Logs: logged via log_audit to establish valid cryptographic hash chain
    log_audit(
        user_name="Dr. Rajesh Sharma",
        user_role="NationalAdmin",
        action_type="SYSTEM_BOOT",
        entity_type="PLATFORM",
        entity_id="SYS",
        description="Federated National Health Resource Intelligence Platform initialized with sovereign node ID NODE-NAT-01",
        ip_address="127.0.0.1"
    )
    log_audit(
        user_name="Elena Rostova",
        user_role="EmergencyCoordinator",
        action_type="ALERT_ESCALATION",
        entity_type="ALERT",
        entity_id="ALT-102",
        description="ICU & Oxygen Critical Saturation alert acknowledged and placed under review",
        ip_address="192.168.1.45"
    )

    print("FNHRIP database seeding complete!")

if __name__ == "__main__":
    seed_database(force=True)
