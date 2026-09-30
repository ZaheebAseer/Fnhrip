import os
import unittest
import json

# Test-only credentials are supplied through environment variables so no real
# passwords or secrets are committed to the repository.
os.environ.setdefault("FNHRIP_SECRET_KEY", "test-only-secret-not-for-production")
os.environ.setdefault("FNHRIP_ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("FNHRIP_OFFICER_PASSWORD", "test-officer-password")
os.environ.setdefault("FNHRIP_OPERATOR_PASSWORD", "test-operator-password")
os.environ.setdefault("FNHRIP_ML_ENGINEER_PASSWORD", "test-ml-password")
os.environ.setdefault("FNHRIP_VIEWER_PASSWORD", "test-viewer-password")

from backend.app import app
from backend.seed_data import seed_database

class TestFNHRIPApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database(force=True)
        cls.client = app.test_client()

    def test_01_health_check(self):
        res = self.client.get('/api/v1/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'HEALTHY')
        self.assertEqual(data['short_name'], 'FNHRIP')

    def test_02_national_metrics(self):
        res = self.client.get('/api/v1/national-metrics')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('facilities_reporting', data)
        self.assertIn('bed_occupancy_rate', data)
        self.assertIn('workforce_coverage_pct', data)
        self.assertGreater(data['facilities_total'], 15)

    def test_03_facilities_and_hierarchy(self):
        res = self.client.get('/api/v1/hierarchy')
        self.assertEqual(res.status_code, 200)
        hierarchy = json.loads(res.data)
        self.assertGreater(len(hierarchy), 0)
        
        res_fac = self.client.get('/api/v1/facilities')
        self.assertEqual(res_fac.status_code, 200)
        facs = json.loads(res_fac.data)
        self.assertGreater(len(facs), 10)

    def test_04_inventory_and_days_of_stock(self):
        res = self.client.get('/api/v1/inventory')
        self.assertEqual(res.status_code, 200)
        inv = json.loads(res.data)
        self.assertGreater(len(inv), 0)
        first = inv[0]
        self.assertIn('days_of_stock', first)
        self.assertIn('risk_level', first)
        self.assertIn(first['risk_level'], ['NORMAL', 'WATCH', 'WARNING', 'CRITICAL'])

    def test_05_inventory_transaction_atomic(self):
        # Post dispensing transaction
        payload = {
            "facility_id": "FAC-001",
            "product_id": "MED-001",
            "transaction_type": "DISPENSING",
            "quantity": 5,
            "reference_doc": "TEST-RX-001",
            "notes": "Emergency room dose",
            "created_by": "test_pharmacist"
        }
        res = self.client.post('/api/v1/inventory/transactions', json=payload)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['quantity'], 5)

    def test_06_demand_forecast_with_provenance(self):
        res = self.client.get('/api/v1/forecasts/demand?facility_id=FAC-001&product_id=MED-001&horizon_days=14')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(len(data['forecast_points']), 14)
        first_pt = data['forecast_points'][0]
        self.assertIn('forecast_value', first_pt)
        self.assertIn('lower_bound', first_pt)
        self.assertIn('upper_bound', first_pt)
        self.assertIn('provenance', data)
        self.assertEqual(data['provenance']['model_version'], 'v2.4-FED')

    def test_07_stockout_prediction(self):
        res = self.client.get('/api/v1/predictions/stockouts')
        self.assertEqual(res.status_code, 200)
        preds = json.loads(res.data)
        self.assertGreater(len(preds), 0)
        p = preds[0]
        self.assertIn('p_stockout_7d', p)
        self.assertIn('p_stockout_14d', p)
        self.assertIn('explainability_drivers', p)

    def test_08_anomaly_detection(self):
        res = self.client.get('/api/v1/anomalies')
        self.assertEqual(res.status_code, 200)
        anomalies = json.loads(res.data)
        self.assertIsInstance(anomalies, list)

    def test_09_recommendations_and_human_approval(self):
        res = self.client.get('/api/v1/recommendations?status=AWAITING_APPROVAL')
        self.assertEqual(res.status_code, 200)
        recs = json.loads(res.data)
        self.assertGreater(len(recs), 0)
        rec_id = recs[0]['recommendation_id']
        
        # Test Human-in-the-Loop approval
        approval_payload = {
            "approved_by": "Dr. Sarah Chen (Chief Medical Officer)",
            "notes": "Approved for emergency mobilization"
        }
        res_app = self.client.post(f'/api/v1/recommendations/{rec_id}/approve', json=approval_payload)
        self.assertEqual(res_app.status_code, 200)
        app_data = json.loads(res_app.data)
        self.assertTrue(app_data['success'])
        self.assertEqual(app_data['status'], 'APPROVED')

    def test_10_what_if_simulator(self):
        payload = {
            "epidemic_surge_pct": 50,
            "supply_cut_pct": 30,
            "warehouse_outage_id": "FAC-002",
            "workforce_absenteeism_pct": 20
        }
        res = self.client.post('/api/v1/simulation/run', json=payload)
        self.assertEqual(res.status_code, 200)
        sim = json.loads(res.data)
        results = sim['simulation_results']
        self.assertIn('time_to_critical_state_days', results)
        self.assertIn('simulated_bed_occupancy_pct', results)
        self.assertIn('recommended_countermeasures', results)
        self.assertGreater(len(results['recommended_countermeasures']), 0)

    def test_11_federated_learning_coordinator(self):
        res = self.client.get('/api/v1/federated/overview')
        self.assertEqual(res.status_code, 200)
        fed = json.loads(res.data)
        self.assertEqual(fed['coordinator_status'], 'ONLINE_ACTIVE')
        self.assertGreater(fed['total_nodes'], 1)
        
        # Run training round
        round_res = self.client.post('/api/v1/federated/run-round', json={"model_id": "MOD-DEMAND-01"})
        self.assertEqual(round_res.status_code, 200)
        round_data = json.loads(round_res.data)
        self.assertTrue(round_data['success'])
        self.assertIn('new_version', round_data)

    def test_12_offline_batch_sync(self):
        sync_payload = {
            "facility_id": "FAC-004",
            "queued_actions": [
                {
                    "action_id": "offline-tx-99",
                    "type": "INVENTORY_TRANSACTION",
                    "product_id": "MED-002",
                    "tx_type": "DISPENSING",
                    "quantity": 2,
                    "notes": "Field clinic prescription"
                }
            ]
        }
        res = self.client.post('/api/v1/sync/batch', json=sync_payload)
        self.assertEqual(res.status_code, 200)
        sync_data = json.loads(res.data)
        self.assertTrue(sync_data['success'])
        self.assertEqual(sync_data['applied'], 1)

    def test_13_audit_chain_cryptographic_integrity(self):
        """Verifies tamper-evident SHA-256 hash chaining links to previous hashes."""
        res = self.client.get('/api/v1/audit/verify')
        self.assertEqual(res.status_code, 200)
        verify_data = json.loads(res.data)
        self.assertTrue(verify_data['verified'])

        # Verify audit logs list returns chain verification status
        logs_res = self.client.get('/api/v1/audit/logs?limit=10')
        self.assertEqual(logs_res.status_code, 200)
        logs_data = json.loads(logs_res.data)
        self.assertIn('items', logs_data)
        self.assertIn('chain_verified', logs_data)
        self.assertTrue(logs_data['chain_verified'])

    def test_14_authentication_jwt_and_roles(self):
        """Tests JWT login, token validation, and role-based access enforcement."""
        # 1. Successful login
        login_res = self.client.post('/api/v1/auth/login', json={
            "username": "officer",
            "password": os.environ["FNHRIP_OFFICER_PASSWORD"]
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        self.assertIn('token', login_data)
        officer_token = login_data['token']

        # 2. Failed login
        bad_login = self.client.post('/api/v1/auth/login', json={
            "username": "officer",
            "password": "wrongpassword"
        })
        self.assertEqual(bad_login.status_code, 401)

        # 3. Authenticated endpoint with token
        me_res = self.client.get('/api/v1/auth/me', headers={"Authorization": f"Bearer {officer_token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = json.loads(me_res.data)
        self.assertEqual(me_data['user']['role'], 'HEALTH_OFFICER')

        # 4. Invalid token rejection
        bad_token_res = self.client.get('/api/v1/auth/me', headers={"Authorization": "Bearer invalid.token.payload"})
        self.assertEqual(bad_token_res.status_code, 401)

        # 5. Role-based restriction: VIEWER cannot execute transactions
        viewer_login = self.client.post('/api/v1/auth/login', json={
            "username": "viewer",
            "password": os.environ["FNHRIP_VIEWER_PASSWORD"]
        })
        viewer_token = json.loads(viewer_login.data)['token']

        forbidden_res = self.client.post(
            '/api/v1/inventory/transactions',
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "facility_id": "FAC-001",
                "product_id": "MED-001",
                "transaction_type": "DISPENSING",
                "quantity": 1
            }
        )
        self.assertEqual(forbidden_res.status_code, 403)

        # 6. Role Switch Endpoint and Alias Normalization
        switch_res = self.client.post('/api/v1/auth/switch-role', json={"role": "Pharmacist"})
        self.assertEqual(switch_res.status_code, 200)
        switch_data = json.loads(switch_res.data)
        self.assertEqual(switch_data['user']['role'], 'PHC_OPERATOR')
        pharmacist_token = switch_data['token']

        # 7. Pharmacist CAN post inventory transaction
        rx_res = self.client.post(
            '/api/v1/inventory/transactions',
            headers={"Authorization": f"Bearer {pharmacist_token}"},
            json={
                "facility_id": "FAC-001",
                "product_id": "MED-001",
                "transaction_type": "DISPENSING",
                "quantity": 2,
                "reference_doc": "RBAC-TEST-RX"
            }
        )
        self.assertEqual(rx_res.status_code, 201)

        # 8. Pharmacist CANNOT approve recommendations (403 Forbidden)
        rx_approve = self.client.post(
            '/api/v1/recommendations/REC-001/approve',
            headers={"Authorization": f"Bearer {pharmacist_token}"},
            json={"notes": "Pharmacist attempt"}
        )
        self.assertEqual(rx_approve.status_code, 403)
        self.assertIn('Access Denied', json.loads(rx_approve.data)['error'])

        # 9. ML Engineer CAN run federated rounds but CANNOT post inventory
        ml_switch = self.client.post('/api/v1/auth/switch-role', json={"role": "MLEngineer"})
        self.assertEqual(ml_switch.status_code, 200)
        ml_token = json.loads(ml_switch.data)['token']

        ml_tx = self.client.post(
            '/api/v1/inventory/transactions',
            headers={"Authorization": f"Bearer {ml_token}"},
            json={
                "facility_id": "FAC-001",
                "product_id": "MED-001",
                "transaction_type": "DISPENSING",
                "quantity": 1
            }
        )
        self.assertEqual(ml_tx.status_code, 403)

    def test_15_api_pagination_and_validation(self):
        """Tests API pagination parameters and safe fallback for malformed input."""
        # Pagination
        res = self.client.get('/api/v1/facilities?page=1&page_size=3')
        self.assertEqual(res.status_code, 200)
        facs = json.loads(res.data)
        self.assertLessEqual(len(facs), 3)

        res_audit = self.client.get('/api/v1/audit/logs?page=1&page_size=4')
        self.assertEqual(res_audit.status_code, 200)
        audit_data = json.loads(res_audit.data)
        self.assertEqual(audit_data['page'], 1)
        self.assertEqual(audit_data['page_size'], 4)
        self.assertLessEqual(len(audit_data['items']), 4)

        # Malformed input validation: must NOT crash with 500 error
        malformed_forecast = self.client.get('/api/v1/forecasts/demand?facility_id=FAC-001&product_id=MED-001&horizon_days=not_a_number')
        self.assertEqual(malformed_forecast.status_code, 200)

        malformed_expiries = self.client.get('/api/v1/inventory/fefo-expiries?days_threshold=malformed')
        self.assertEqual(malformed_expiries.status_code, 200)

    def test_16_ai_ml_upgrades(self):
        """Tests Holt-Winters demand forecasting, Monte Carlo simulation, and empirical z-scores."""
        # 1. Holt-Winters Forecasting
        forecast_res = self.client.get('/api/v1/forecasts/demand?facility_id=FAC-001&product_id=MED-001&horizon_days=14')
        self.assertEqual(forecast_res.status_code, 200)
        fc_data = json.loads(forecast_res.data)
        self.assertIn('algorithm', fc_data['provenance'])
        self.assertIn('Holt', fc_data['provenance']['algorithm'])

        # 2. Monte Carlo Stockout Predictor
        stockout_res = self.client.get('/api/v1/predictions/stockouts')
        self.assertEqual(stockout_res.status_code, 200)
        stockouts = json.loads(stockout_res.data)
        first_pred = stockouts[0]
        self.assertIn('Monte Carlo', first_pred.get('simulation_method', ''))
        self.assertGreaterEqual(first_pred['p_stockout_7d'], 0.0)
        self.assertLessEqual(first_pred['p_stockout_7d'], 1.0)

        # 3. Empirical Z-Score Anomaly Detection
        anomalies_res = self.client.get('/api/v1/anomalies')
        self.assertEqual(anomalies_res.status_code, 200)
        anomalies = json.loads(anomalies_res.data)
        for a in anomalies:
            self.assertIn('z_score', a)
            self.assertIsInstance(a['z_score'], (int, float))

if __name__ == '__main__':
    unittest.main()
