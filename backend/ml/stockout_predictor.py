import datetime
import numpy as np
from backend.database import db_session

def monte_carlo_stockout_prob(current_stock, mean_burn, days_target, num_simulations=1000):
    """Computes probabilistic stockout risk using Monte Carlo stochastic demand trajectory sampling."""
    if current_stock <= 0:
        return 1.0
    if mean_burn <= 0:
        return 0.0
    
    # Model daily demand as non-negative stochastic distribution with clinical variance
    std_burn = max(0.35 * mean_burn, 1.0)
    daily_draws = np.random.normal(loc=mean_burn, scale=std_burn, size=(num_simulations, days_target))
    daily_draws = np.maximum(0, daily_draws)
    cumulative_demand = np.sum(daily_draws, axis=1)
    stockouts = np.sum(cumulative_demand >= current_stock)
    return round(float(stockouts / num_simulations), 2)

def predict_stockout_risks(facility_id=None, district_id=None, limit=50):
    with db_session() as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            p.product_id, p.generic_name, p.brand_name, p.category, p.default_lead_time_days, p.safety_stock,
            f.facility_id, f.name as facility_name, f.facility_type,
            d.district_id, d.name as district_name,
            COALESCE(SUM(b.available_quantity), 0) as available_stock,
            (
                SELECT COALESCE(ROUND(AVG(c.units_consumed), 1), 3.0)
                FROM historical_consumption c
                WHERE c.facility_id = f.facility_id AND c.product_id = p.product_id
                AND c.record_date >= date('now', '-30 days')
            ) as daily_burn_rate
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
            
        query += " GROUP BY p.product_id, f.facility_id"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        
    now = datetime.datetime.now()
    predictions = []
    
    for r in rows:
        avail = float(r['available_stock'])
        burn = float(r['daily_burn_rate'] or 2.0)
        lead_days = int(r['default_lead_time_days'] or 5)
        safety = float(r['safety_stock'] or 20)
        
        days_of_stock = round(avail / burn, 1) if burn > 0 else 999.0
        
        # Monte Carlo stochastic stockout probabilities across 7d, 14d, 30d windows
        p_7d = monte_carlo_stockout_prob(avail, burn, 7)
        p_14d = monte_carlo_stockout_prob(avail, burn, 14)
        p_30d = monte_carlo_stockout_prob(avail, burn, 30)
        
        # Estimated stockout date
        if days_of_stock < 999:
            stockout_dt = (now + datetime.timedelta(days=int(days_of_stock))).strftime("%Y-%m-%d")
        else:
            stockout_dt = "No Stockout Foreseen (>180d)"
            
        # Risk classification
        if days_of_stock <= 5.0 or p_7d >= 0.7:
            risk_tier = "CRITICAL"
            badge_class = "risk-critical"
        elif days_of_stock <= 14.0 or p_14d >= 0.6:
            risk_tier = "WARNING"
            badge_class = "risk-warning"
        elif days_of_stock <= 25.0 or p_30d >= 0.5:
            risk_tier = "WATCH"
            badge_class = "risk-watch"
        else:
            risk_tier = "NORMAL"
            badge_class = "risk-normal"
            
        # Explainability drivers
        drivers = []
        if days_of_stock < lead_days:
            drivers.append(f"Days of stock ({days_of_stock}d) is strictly less than supplier lead time ({lead_days}d).")
        if avail < safety:
            drivers.append(f"Available stock ({int(avail)}) has breached mandatory safety buffer ({int(safety)}).")
        if burn > 5.0:
            drivers.append(f"Consumption velocity is elevated ({burn} units/day).")
        if not drivers:
            drivers.append("Stock levels sufficient for normal operational consumption.")
            
        predictions.append({
            "facility_id": r['facility_id'],
            "facility_name": r['facility_name'],
            "facility_type": r['facility_type'],
            "district_name": r['district_name'],
            "product_id": r['product_id'],
            "generic_name": r['generic_name'],
            "category": r['category'],
            "available_stock": int(avail),
            "daily_burn_rate": burn,
            "days_of_stock": days_of_stock,
            "lead_time_days": lead_days,
            "p_stockout_7d": p_7d,
            "p_stockout_14d": p_14d,
            "p_stockout_30d": p_30d,
            "expected_stockout_date": stockout_dt,
            "risk_tier": risk_tier,
            "badge_class": badge_class,
            "explainability_drivers": drivers,
            "simulation_method": "Monte Carlo (N=1000 paths)"
        })
        
    # Sort with Critical / High probability on top
    predictions.sort(key=lambda x: (
        0 if x['risk_tier'] == 'CRITICAL' else (1 if x['risk_tier'] == 'WARNING' else (2 if x['risk_tier'] == 'WATCH' else 3)),
        x['days_of_stock']
    ))
    
    return predictions[:limit]
