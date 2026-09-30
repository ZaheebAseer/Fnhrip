# FNHRIP Database Schema Specification

### Relational Schema (PostgreSQL / SQLite Compatible)

#### 1. Administrative Hierarchy & Facilities
- `countries (country_id, country_code, name, currency, timezone, active)`
- `regions (region_id, country_id, name, code, coordinates_geo)`
- `districts (district_id, region_id, name, code, population, catchment_pop)`
- `facilities (facility_id, district_id, name, code, facility_type, latitude, longitude, catchment_population, operational_status, total_storage_sqft, cold_chain_liters, total_beds, is_reporting, last_sync_time)`

#### 2. Products & Master Catalog
- `product_categories (category_id, name, description)`
- `products (product_id, category_id, code, generic_name, brand_name, therapeutic_class, strength, dosage_form, uom, pack_size, is_essential, is_cold_chain, is_controlled, min_stock, max_stock, safety_stock, default_lead_days)`

#### 3. Inventory & FEFO Batches
- `inventory_batches (batch_id, facility_id, product_id, batch_number, quantity, reserved_quantity, available_quantity, unit_cost, manufacturing_date, expiry_date, storage_condition, status)`
- `inventory_transactions (transaction_id, facility_id, product_id, batch_id, transaction_type, quantity, balance_after, reference_doc, notes, created_by, created_at)`
  * Transaction Types: `RECEIPT`, `DISPENSING`, `ISSUE`, `TRANSFER`, `ADJUSTMENT`, `LOSS`, `DAMAGE`, `EXPIRY`, `RESERVATION`, `RELEASE`

#### 4. Healthcare Capacity & Workforce
- `bed_statuses (status_id, facility_id, total_beds, functional_beds, occupied_beds, icu_beds, icu_occupied, oxygen_beds, oxygen_occupied, ventilators_total, ventilators_in_use, updated_at)`
- `worker_roles (role_id, role_code, title, required_ratio_per_bed)`
- `workforce_attendance (record_id, facility_id, role_id, scheduled_count, present_count, absent_count, on_leave_count, emergency_deployed_count, shift_date, shift_type)`

#### 5. Alerts & Decision Support
- `alerts (alert_id, facility_id, district_id, severity, alert_type, resource_name, detected_at, reason, evidence_json, probability, recommended_action, status, owner_id)`
  * Severities: `INFO`, `WATCH`, `WARNING`, `CRITICAL`, `EMERGENCY`
  * Lifecycles: `CREATED`, `ACKNOWLEDGED`, `UNDER_REVIEW`, `ACTIONED`, `RESOLVED`, `DISMISSED`
- `recommendations (recommendation_id, recommendation_type, priority, source_facility_id, dest_facility_id, product_id, quantity, expected_destination_days, confidence_score, reasons_json, status, approved_by, approved_at, rejection_reason)`

#### 6. AI Models & Federated Intelligence
- `ml_models (model_id, name, model_family, current_version, task_type, target_metric, last_trained_at, status)`
- `federated_rounds (round_id, model_id, round_number, start_time, end_time, participating_nodes_count, global_loss, convergence_score, status)`
- `data_quality_scores (score_id, facility_id, completeness_pct, validity_pct, timeliness_pct, consistency_pct, overall_score, evaluation_date)`
- `audit_logs (log_id, user_id, action_type, entity_name, entity_id, payload_before, payload_after, ip_address, timestamp, tamper_hash)`
