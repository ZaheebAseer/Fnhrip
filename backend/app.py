import os
import json
from flask import Flask, request, jsonify, send_from_directory, send_file, g
from backend.config import Config, BASE_DIR
from backend.auth import require_auth, authenticate_user, switch_role, ROLE_PROFILES
from backend.services.facility_service import get_hierarchy, get_facilities, get_facility_detail, get_national_metrics
from backend.services.inventory_service import get_products, get_inventory_summary, get_facility_batches, get_fefo_expiries, record_transaction
from backend.services.capacity_service import get_bed_capacities
from backend.services.workforce_service import get_workforce_summary, record_attendance
from backend.services.alert_service import get_alerts, update_alert_status, create_alert
from backend.services.audit_service import log_audit, get_audit_logs, verify_audit_chain
from backend.services.sync_service import process_offline_batch
from backend.ml.forecasting import get_demand_forecast
from backend.ml.stockout_predictor import predict_stockout_risks
from backend.ml.anomaly_detector import detect_anomalies
from backend.ml.redistribution_optimizer import get_recommendations, generate_redistribution_recommendations, approve_recommendation, reject_recommendation
from backend.ml.simulation_engine import run_what_if_simulation
from backend.ml.federated_coordinator import get_federated_overview, execute_federated_round

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config.from_object(Config)

# ----------------- Input Validation Helpers -----------------
def safe_int(val, default=0, min_val=None, max_val=None):
    """Safely converts input to integer with bounds clamping and fallback."""
    try:
        if val is None:
            return default
        res = int(val)
        if min_val is not None:
            res = max(min_val, res)
        if max_val is not None:
            res = min(max_val, res)
        return res
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0, min_val=None, max_val=None):
    """Safely converts input to float with bounds clamping and fallback."""
    try:
        if val is None:
            return default
        res = float(val)
        if min_val is not None:
            res = max(min_val, res)
        if max_val is not None:
            res = min(max_val, res)
        return res
    except (ValueError, TypeError):
        return default

# ----------------- CORS & Preflight -----------------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,PATCH,DELETE,OPTIONS'
    return response

@app.route('/api/<path:dummy>', methods=['OPTIONS'])
def handle_options(dummy):
    return ('', 204)

# ----------------- Global Error Handlers -----------------
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad request", "details": str(e)}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    return jsonify({"error": "An unexpected error occurred", "message": str(e)}), 500

# ----------------- Authentication Routes -----------------
@app.route('/api/v1/auth/login', methods=['POST'])
def api_auth_login():
    payload = request.get_json(silent=True) or {}
    username = payload.get('username') or request.form.get('username')
    password = payload.get('password') or request.form.get('password')
    
    if not username or not password:
        return jsonify({"error": "Both 'username' and 'password' are required"}), 400
        
    auth_result = authenticate_user(username, password)
    if not auth_result:
        return jsonify({"error": "Invalid username or password"}), 401
        
    return jsonify({
        "success": True,
        "token": auth_result['token'],
        "user": auth_result['user']
    }), 200

@app.route('/api/v1/auth/me', methods=['GET'])
@require_auth()
def api_auth_me():
    return jsonify({
        "authenticated": True,
        "user": getattr(g, 'current_user', None)
    }), 200

@app.route('/api/v1/auth/switch-role', methods=['POST'])
def api_auth_switch_role():
    payload = request.get_json(silent=True) or {}
    role = payload.get('role') or payload.get('role_alias') or request.args.get('role') or 'ADMIN'
    res = switch_role(role)
    return jsonify({
        "success": True,
        "token": res['token'],
        "user": res['user']
    }), 200

@app.route('/api/v1/auth/roles', methods=['GET'])
def api_auth_roles():
    return jsonify({
        "roles": ROLE_PROFILES
    }), 200

# ----------------- Frontend & Static Routes -----------------
@app.route('/')
def index():
    return send_file(os.path.join(FRONTEND_DIR, "index.html"))

@app.route('/login')
def login_page():
    return send_file(os.path.join(FRONTEND_DIR, "login.html"))

@app.route('/<path:filename>')
def static_files(filename):
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIR, filename)
    return send_file(os.path.join(FRONTEND_DIR, "index.html"))

# ----------------- Health & OpenAPI Spec -----------------
@app.route('/api/v1/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "HEALTHY",
        "platform": "Federated National Health Resource Intelligence Platform",
        "short_name": "FNHRIP",
        "version": Config.VERSION,
        "country": Config.COUNTRY_NAME,
        "federation_node": "NODE-NAT-01"
    })

@app.route('/api/v1/openapi.json', methods=['GET'])
def openapi_spec():
    spec_path = os.path.join(BASE_DIR, "openapi.json")
    if os.path.exists(spec_path):
        with open(spec_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({"openapi": "3.0.0", "info": {"title": "FNHRIP REST API", "version": Config.VERSION}})

# ----------------- National & Facilities -----------------
@app.route('/api/v1/national-metrics', methods=['GET'])
def api_national_metrics():
    metrics = get_national_metrics()
    return jsonify(metrics)

@app.route('/api/v1/hierarchy', methods=['GET'])
def api_hierarchy():
    data = get_hierarchy()
    return jsonify(data)

@app.route('/api/v1/facilities', methods=['GET'])
def api_facilities():
    did = request.args.get('district_id')
    ftype = request.args.get('type')
    status = request.args.get('status')
    page = safe_int(request.args.get('page'), default=1, min_val=1)
    page_size = safe_int(request.args.get('page_size'), default=None, min_val=1, max_val=200) if 'page_size' in request.args else None
    
    data = get_facilities(district_id=did, facility_type=ftype, status=status, page=page, page_size=page_size)
    return jsonify(data)

@app.route('/api/v1/facilities/<facility_id>', methods=['GET'])
def api_facility_detail(facility_id):
    data = get_facility_detail(facility_id)
    if not data:
        return jsonify({"error": "Facility not found"}), 404
    return jsonify(data)

# ----------------- Products & Inventory -----------------
@app.route('/api/v1/products', methods=['GET'])
def api_products():
    data = get_products()
    return jsonify(data)

@app.route('/api/v1/inventory', methods=['GET'])
def api_inventory():
    fid = request.args.get('facility_id')
    did = request.args.get('district_id')
    page = safe_int(request.args.get('page'), default=1, min_val=1)
    page_size = safe_int(request.args.get('page_size'), default=None, min_val=1, max_val=500) if 'page_size' in request.args else None
    data = get_inventory_summary(facility_id=fid, district_id=did, page=page, page_size=page_size)
    return jsonify(data)

@app.route('/api/v1/inventory/facility/<facility_id>/batches', methods=['GET'])
def api_facility_batches(facility_id):
    data = get_facility_batches(facility_id)
    return jsonify(data)

@app.route('/api/v1/inventory/fefo-expiries', methods=['GET'])
def api_fefo_expiries():
    days = safe_int(request.args.get('days_threshold'), default=45, min_val=1, max_val=730)
    data = get_fefo_expiries(days_threshold=days)
    return jsonify(data)

@app.route('/api/v1/inventory/transactions', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER', 'PHC_OPERATOR'])
def api_post_transaction():
    payload = request.get_json(force=True) or {}
    operator_name = getattr(g, 'current_user', {}).get('name', payload.get('created_by', 'api_user'))
    
    qty = safe_int(payload.get('quantity'), default=1, min_val=1)
    res = record_transaction(
        facility_id=payload.get('facility_id'),
        product_id=payload.get('product_id'),
        batch_id=payload.get('batch_id'),
        tx_type=payload.get('transaction_type', 'DISPENSING'),
        quantity=qty,
        reference_doc=payload.get('reference_doc'),
        notes=payload.get('notes'),
        created_by=operator_name
    )
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res), 201

# ----------------- Bed Capacity & Workforce -----------------
@app.route('/api/v1/beds', methods=['GET'])
def api_beds():
    did = request.args.get('district_id')
    data = get_bed_capacities(district_id=did)
    return jsonify(data)

@app.route('/api/v1/workforce', methods=['GET'])
def api_workforce():
    fid = request.args.get('facility_id')
    did = request.args.get('district_id')
    data = get_workforce_summary(facility_id=fid, district_id=did)
    return jsonify(data)

@app.route('/api/v1/workforce/attendance', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER', 'PHC_OPERATOR'])
def api_post_attendance():
    payload = request.get_json(force=True) or {}
    res = record_attendance(
        facility_id=payload.get('facility_id'),
        role_type=payload.get('role_type', 'Nurse'),
        scheduled=safe_int(payload.get('scheduled'), default=1, min_val=0),
        present=safe_int(payload.get('present'), default=1, min_val=0),
        absent=safe_int(payload.get('absent'), default=0, min_val=0),
        leave=safe_int(payload.get('leave'), default=0, min_val=0),
        shift_date=payload.get('shift_date'),
        shift_type=payload.get('shift_type', 'DAY')
    )
    return jsonify(res), 200

# ----------------- Alerts -----------------
@app.route('/api/v1/alerts', methods=['GET'])
def api_alerts():
    sev = request.args.get('severity')
    status = request.args.get('status')
    fid = request.args.get('facility_id')
    did = request.args.get('district_id')
    page = safe_int(request.args.get('page'), default=1, min_val=1)
    page_size = safe_int(request.args.get('page_size'), default=None, min_val=1, max_val=200) if 'page_size' in request.args else None
    
    data = get_alerts(severity=sev, status=status, facility_id=fid, district_id=did, page=page, page_size=page_size)
    return jsonify(data)

@app.route('/api/v1/alerts/<alert_id>/status', methods=['PATCH'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER'])
def api_update_alert(alert_id):
    payload = request.get_json(force=True) or {}
    new_status = payload.get('status')
    owner = payload.get('owner') or getattr(g, 'current_user', {}).get('name')
    res = update_alert_status(alert_id, new_status, owner=owner)
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res)

# ----------------- Predictive AI & Early Warning -----------------
@app.route('/api/v1/forecasts/demand', methods=['GET'])
def api_forecast():
    fid = request.args.get('facility_id', 'FAC-001')
    pid = request.args.get('product_id', 'MED-001')
    horizon = safe_int(request.args.get('horizon_days'), default=30, min_val=1, max_val=180)
    data = get_demand_forecast(facility_id=fid, product_id=pid, horizon_days=horizon)
    return jsonify(data)

@app.route('/api/v1/predictions/stockouts', methods=['GET'])
def api_stockout_predictions():
    fid = request.args.get('facility_id')
    did = request.args.get('district_id')
    limit = safe_int(request.args.get('limit'), default=50, min_val=1, max_val=200)
    data = predict_stockout_risks(facility_id=fid, district_id=did, limit=limit)
    return jsonify(data)

@app.route('/api/v1/anomalies', methods=['GET'])
def api_anomalies():
    data = detect_anomalies()
    return jsonify(data)

# ----------------- Recommendations & Human Approval -----------------
@app.route('/api/v1/recommendations', methods=['GET'])
def api_recommendations():
    status = request.args.get('status')
    page = safe_int(request.args.get('page'), default=1, min_val=1)
    page_size = safe_int(request.args.get('page_size'), default=None, min_val=1, max_val=200) if 'page_size' in request.args else None
    data = get_recommendations(status=status, page=page, page_size=page_size)
    return jsonify(data)

@app.route('/api/v1/recommendations/generate', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER', 'ML_ENGINEER'])
def api_generate_recommendations():
    new_recs = generate_redistribution_recommendations()
    return jsonify({"success": True, "generated_count": len(new_recs), "recommendation_ids": new_recs})

@app.route('/api/v1/recommendations/<rec_id>/approve', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER'])
def api_approve_recommendation(rec_id):
    payload = request.get_json(force=True) or {}
    approved_by = getattr(g, 'current_user', {}).get('name', payload.get('approved_by', 'Authorized Health Officer'))
    notes = payload.get('notes', 'Approved by Operations Cell')
    res = approve_recommendation(rec_id, approved_by=approved_by, approval_notes=notes)
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res)

@app.route('/api/v1/recommendations/<rec_id>/reject', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER'])
def api_reject_recommendation(rec_id):
    payload = request.get_json(force=True) or {}
    rejected_by = getattr(g, 'current_user', {}).get('name', payload.get('rejected_by', 'Authorized Health Officer'))
    notes = payload.get('notes', 'Clinical priority override')
    res = reject_recommendation(rec_id, rejected_by=rejected_by, rejection_notes=notes)
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res)

# ----------------- What-If Emergency Simulator -----------------
@app.route('/api/v1/simulation/run', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER', 'ML_ENGINEER'])
def api_run_simulation():
    payload = request.get_json(force=True) or {}
    surge = safe_int(payload.get('epidemic_surge_pct'), default=30, min_val=0, max_val=500)
    supply_cut = safe_int(payload.get('supply_cut_pct'), default=20, min_val=0, max_val=100)
    wh_outage = payload.get('warehouse_outage_id')
    wf_absent = safe_int(payload.get('workforce_absenteeism_pct'), default=15, min_val=0, max_val=100)
    target_dist = payload.get('district_id')
    
    res = run_what_if_simulation(
        epidemic_surge_pct=surge,
        supply_cut_pct=supply_cut,
        warehouse_outage_id=wh_outage,
        workforce_absenteeism_pct=wf_absent,
        target_district_id=target_dist
    )
    return jsonify(res)

# ----------------- Federated Intelligence -----------------
@app.route('/api/v1/federated/overview', methods=['GET'])
def api_federated_overview():
    data = get_federated_overview()
    return jsonify(data)

@app.route('/api/v1/federated/run-round', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'ML_ENGINEER'])
def api_run_federated_round():
    payload = request.get_json(force=True) or {}
    mid = payload.get('model_id', 'MOD-DEMAND-01')
    triggered_by = getattr(g, 'current_user', {}).get('name', payload.get('triggered_by', 'FederatedCoordinator'))
    res = execute_federated_round(model_id=mid, triggered_by=triggered_by)
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res)

# ----------------- Offline Sync -----------------
@app.route('/api/v1/sync/batch', methods=['POST'])
@require_auth(allowed_roles=['ADMIN', 'HEALTH_OFFICER', 'PHC_OPERATOR'])
def api_sync_batch():
    payload = request.get_json(force=True) or {}
    fid = payload.get('facility_id')
    actions = payload.get('queued_actions', [])
    res = process_offline_batch(facility_id=fid, queued_actions=actions)
    if not res.get('success'):
        return jsonify(res), 400
    return jsonify(res)

# ----------------- Audit Logs & Cryptographic Verification -----------------
@app.route('/api/v1/audit/logs', methods=['GET'])
def api_audit_logs():
    limit = safe_int(request.args.get('limit'), default=50, min_val=1, max_val=500)
    page = safe_int(request.args.get('page'), default=1, min_val=1)
    page_size = safe_int(request.args.get('page_size'), default=limit, min_val=1, max_val=500)
    data = get_audit_logs(limit=limit, page=page, page_size=page_size)
    return jsonify(data)

@app.route('/api/v1/audit/verify', methods=['GET'])
def api_audit_verify():
    result = verify_audit_chain()
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting FNHRIP Sovereign Platform Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

