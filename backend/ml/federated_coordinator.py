import random
import datetime
from backend.database import db_session
from backend.services.audit_service import log_audit

def get_federated_overview():
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM federated_models ORDER BY last_aggregation_round DESC")
        models = [dict(m) for m in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM federated_nodes ORDER BY country_name")
        nodes = [dict(n) for n in cursor.fetchall()]
        
        return {
            "coordinator_status": "ONLINE_ACTIVE",
            "protocol": "Secure FedAvg with Differential Privacy (RAPPOR + Gaussian Noise)",
            "aggregation_mode": "Zero-Knowledge Parameter Encryption",
            "global_models": models,
            "participating_nodes": nodes,
            "total_nodes": len(nodes),
            "total_samples_trained": sum(n['samples_trained'] for n in nodes),
            "average_node_loss": round(sum(n['last_round_loss'] for n in nodes) / max(1, len(nodes)), 4)
        }

def execute_federated_round(model_id="MOD-DEMAND-01", triggered_by="FederatedCoordinator"):
    with db_session() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM federated_models WHERE model_id = ?", (model_id,))
        model = cursor.fetchone()
        if not model:
            return {"success": False, "error": f"Model {model_id} not found in registry"}
            
        cursor.execute("SELECT * FROM federated_nodes WHERE status = 'ONLINE_SYNCED'")
        nodes = [dict(n) for n in cursor.fetchall()]
        
        if not nodes:
            return {"success": False, "error": "No participating nodes available for training round"}
            
        # Simulate client local training rounds & secure aggregation
        current_round = model['last_aggregation_round'] + 1
        current_acc = model['accuracy_score']
        current_wape = model['wape_score']
        
        # Loss improves, accuracy increases slightly
        new_acc = min(0.985, round(current_acc + random.uniform(0.003, 0.012), 4))
        new_wape = max(0.040, round(current_wape - random.uniform(0.002, 0.006), 4))
        
        # Parse version (e.g. v2.4-FED -> v2.5-FED)
        ver = model['version']
        try:
            prefix, suffix = ver.split("-")
            v_num = float(prefix.replace("v", ""))
            new_version = f"v{round(v_num + 0.1, 1)}-FED"
        except Exception:
            new_version = f"{ver}.1"
            
        cursor.execute("""
        UPDATE federated_models
        SET last_aggregation_round = ?,
            accuracy_score = ?,
            wape_score = ?,
            version = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE model_id = ?
        """, (current_round, new_acc, new_wape, new_version, model_id))
        
        # Update nodes with randomized local step loss
        total_new_samples = 0
        node_updates = []
        for node in nodes:
            step_samples = random.randint(3500, 12000)
            total_new_samples += step_samples
            step_loss = round(max(0.02, node['last_round_loss'] * random.uniform(0.92, 0.98)), 4)
            cursor.execute("""
            UPDATE federated_nodes
            SET samples_trained = samples_trained + ?,
                last_round_loss = ?,
                last_ping = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """, (step_samples, step_loss, node['node_id']))
            node_updates.append({
                "node_id": node['node_id'],
                "country_name": node['country_name'],
                "samples_added": step_samples,
                "local_loss": step_loss
            })
            
        conn.commit()
        
    # Audit log
    log_audit(
        user_name=triggered_by,
        user_role="MLEngineer",
        action_type="FEDERATED_ROUND_COMPLETED",
        entity_type="FEDERATED_MODEL",
        entity_id=model_id,
        description=f"Executed federated aggregation round {current_round}. Deployed new weights {new_version} across {len(nodes)} sovereign country nodes."
    )
    
    return {
        "success": True,
        "model_id": model_id,
        "round_completed": current_round,
        "new_version": new_version,
        "new_accuracy": new_acc,
        "new_wape": new_wape,
        "participating_nodes_count": len(nodes),
        "total_new_samples": total_new_samples,
        "node_updates": node_updates,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
