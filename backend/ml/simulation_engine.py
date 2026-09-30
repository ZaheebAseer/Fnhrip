import math
from backend.database import db_session

def run_what_if_simulation(
    epidemic_surge_pct=30,      # e.g., +30% demand
    supply_cut_pct=20,          # e.g., -20% incoming shipments
    warehouse_outage_id=None,   # e.g., 'FAC-002' disabled
    workforce_absenteeism_pct=15, # e.g., 15% staff down
    target_district_id=None
):
    with db_session() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch current facilities, beds, and inventory
        query_fac = "SELECT * FROM facilities WHERE operational_status = 'ACTIVE'"
        params = []
        if target_district_id:
            query_fac += " AND district_id = ?"
            params.append(target_district_id)
        cursor.execute(query_fac, params)
        facilities = [dict(f) for f in cursor.fetchall()]
        
        # Beds
        cursor.execute("""
        SELECT b.*, f.district_id 
        FROM bed_statuses b 
        JOIN facilities f ON b.facility_id = f.facility_id
        """)
        beds = [dict(b) for b in cursor.fetchall()]
        
        # Critical inventory items (Insulin, Oxygen, Antibiotics, IV fluids)
        cursor.execute("""
        SELECT b.facility_id, b.product_id, p.generic_name, SUM(b.available_quantity) as total_stock
        FROM inventory_batches b
        JOIN products p ON b.product_id = p.product_id
        GROUP BY b.facility_id, b.product_id
        """)
        inventory = [dict(i) for i in cursor.fetchall()]
    
    # Baseline calculations
    surge_multiplier = 1.0 + (float(epidemic_surge_pct) / 100.0)
    supply_reduction = float(supply_cut_pct) / 100.0
    staff_loss_pct = float(workforce_absenteeism_pct) / 100.0
    
    total_functional_beds = sum(b['functional_beds'] for b in beds if b['functional_beds'])
    current_occupied = sum(b['occupied_beds'] for b in beds if b['occupied_beds'])
    current_icu_occ = sum(b['icu_occupied'] for b in beds if b['icu_occupied'])
    total_icu_beds = sum(b['icu_beds'] for b in beds if b['icu_beds'])
    total_o2_beds = sum(b['oxygen_beds'] for b in beds if b['oxygen_beds'])
    current_o2_occ = sum(b['oxygen_occupied'] for b in beds if b['oxygen_occupied'])
    
    # Simulated Impact
    # 1. Beds: admissions surge with epidemic
    simulated_bed_demand = int(current_occupied * surge_multiplier)
    # Reduced functional capacity due to workforce absenteeism (Section 12: operational capacity)
    effective_functional_beds = int(total_functional_beds * (1.0 - (staff_loss_pct * 0.5)))
    bed_deficit = max(0, simulated_bed_demand - effective_functional_beds)
    simulated_bed_occupancy_pct = min(150.0, round((simulated_bed_demand / effective_functional_beds * 100) if effective_functional_beds > 0 else 100, 1))
    
    # 2. ICU stress
    simulated_icu_demand = int(current_icu_occ * (1.0 + (surge_multiplier - 1.0) * 1.4))
    icu_deficit = max(0, simulated_icu_demand - total_icu_beds)
    simulated_icu_occupancy_pct = min(180.0, round((simulated_icu_demand / total_icu_beds * 100) if total_icu_beds > 0 else 100, 1))
    
    # 3. Oxygen stress
    simulated_o2_demand = int(current_o2_occ * surge_multiplier)
    o2_deficit = max(0, simulated_o2_demand - total_o2_beds)
    estimated_cylinder_shortage = int(o2_deficit * 2.8)
    
    # 4. Inventory stockout acceleration
    # Warehouses disabled?
    disabled_warehouse_name = None
    if warehouse_outage_id:
        for f in facilities:
            if f['facility_id'] == warehouse_outage_id:
                disabled_warehouse_name = f['name']
                break
                
    critical_stockout_facilities = 0
    at_risk_facilities_list = []
    
    fac_inv_map = {}
    for inv in inventory:
        fid = inv['facility_id']
        if fid not in fac_inv_map:
            fac_inv_map[fid] = []
        fac_inv_map[fid].append(inv)
        
    for f in facilities:
        if f['facility_type'] == 'Warehouse':
            continue
        fid = f['facility_id']
        items = fac_inv_map.get(fid, [])
        low_items = [i for i in items if i['total_stock'] < int(25 * surge_multiplier)]
        if len(low_items) >= 2 or warehouse_outage_id:
            critical_stockout_facilities += 1
            at_risk_facilities_list.append({
                "facility_id": fid,
                "facility_name": f['name'],
                "district_id": f['district_id'],
                "critical_items_count": len(low_items),
                "simulated_days_to_failure": max(1.5, round(7.0 / surge_multiplier, 1))
            })
            
    # Days to critical state
    if simulated_icu_occupancy_pct >= 100.0 or bed_deficit > 0:
        time_to_critical_days = 2.4
    elif simulated_bed_occupancy_pct >= 90.0:
        time_to_critical_days = 5.8
    else:
        time_to_critical_days = 11.5
        
    # Countermeasures recommended by AI
    recommended_countermeasures = []
    if bed_deficit > 0:
        recommended_countermeasures.append(f"Activate {bed_deficit + 40} emergency surge beds in designated community halls and step-down CHCs.")
    if icu_deficit > 0:
        recommended_countermeasures.append(f"Mobilize {icu_deficit} portable transport ventilators and initiate triage diversion protocol.")
    if estimated_cylinder_shortage > 0:
        recommended_countermeasures.append(f"Emergency requisition of {estimated_cylinder_shortage} D-Type medical oxygen cylinders from regional industrial suppliers.")
    if staff_loss_pct > 0.1:
        recommended_countermeasures.append(f"Recall reserve medical corps and cancel elective clinic leaves to offset {int(staff_loss_pct*100)}% staffing loss.")
    if warehouse_outage_id:
        recommended_countermeasures.append(f"Redirect all supply chain routing around disabled depot '{disabled_warehouse_name or warehouse_outage_id}'.")
        
    return {
        "parameters": {
            "epidemic_surge_pct": epidemic_surge_pct,
            "supply_cut_pct": supply_cut_pct,
            "warehouse_outage": disabled_warehouse_name or warehouse_outage_id or "None (Full Network Operational)",
            "workforce_absenteeism_pct": workforce_absenteeism_pct
        },
        "simulation_results": {
            "time_to_critical_state_days": time_to_critical_days,
            "simulated_bed_occupancy_pct": simulated_bed_occupancy_pct,
            "total_bed_deficit": bed_deficit,
            "simulated_icu_occupancy_pct": simulated_icu_occupancy_pct,
            "icu_deficit": icu_deficit,
            "oxygen_shortage_cylinders": estimated_cylinder_shortage,
            "critical_stockout_facilities_count": critical_stockout_facilities,
            "total_facilities_evaluated": len(facilities),
            "at_risk_facilities": at_risk_facilities_list[:8],
            "recommended_countermeasures": recommended_countermeasures
        }
    }
