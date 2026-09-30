# FNHRIP REST API Specification v1.1

### Authentication & Role-Based Access Control
- `Authorization: Bearer <JWT_TOKEN>`
- `Content-Type: application/json`
- **Supported Roles**:
  - `ADMIN`: Full administrative and configuration control
  - `HEALTH_OFFICER`: Emergency transfers, alert resolution, recommendation approval/rejection
  - `PHC_OPERATOR`: Field dispensing, inventory adjustments, shift attendance records
  - `ML_ENGINEER`: Federated rounds, model hyperparameter tuning, simulation execution
  - `VIEWER`: Read-only operational dashboards and public health monitoring

### Endpoints Overview

#### 1. Authentication & Security
- `POST /api/v1/auth/login` - Authenticate username/password and acquire signed JWT token
- `GET /api/v1/auth/me` - Inspect current authenticated user and role permissions

#### 2. Facility & Hierarchy
- `GET /api/v1/hierarchy` - Full geographic tree (Country -> Region -> District -> Facilities)
- `GET /api/v1/facilities` - List facilities with filters (`district_id`, `type`, `status`, `page`, `page_size`)
- `GET /api/v1/facilities/<id>` - Single facility detail, capacity, staff & operational score

#### 3. Inventory & Stock
- `GET /api/v1/products` - Master medical product catalog
- `GET /api/v1/inventory` - Multi-facility inventory summaries with days-of-stock & stockout risk (`page`, `page_size`)
- `GET /api/v1/inventory/facility/<facility_id>/batches` - Granular batch-level stock & FEFO expiry alerts
- `POST /api/v1/inventory/transactions` - Post receipt, dispensing, transfer, expiry write-off *(Requires auth: `ADMIN`, `HEALTH_OFFICER`, `PHC_OPERATOR`)*
- `GET /api/v1/inventory/fefo-expiries` - Expiring stock alerts within specified days threshold

#### 4. Capacity & Workforce
- `GET /api/v1/beds` - Bed & ICU occupancy rates across facilities
- `GET /api/v1/workforce` - Staffing coverage, scheduled vs present, shortage ratios
- `POST /api/v1/workforce/attendance` - Submit shift attendance records *(Requires auth)*

#### 5. Predictive AI & Early Warning
- `GET /api/v1/forecasts/demand` - Holt-Winters Exponential Smoothing demand forecast with clinical weekly seasonality and dynamic confidence bounds
- `GET /api/v1/predictions/stockouts` - Monte Carlo stochastic demand trajectory simulation (1,000 paths) estimating stockout probabilities (7d, 14d, 30d)
- `GET /api/v1/anomalies` - Empirical statistical z-score anomaly detection across clinical consumption surges and intensive care saturation

#### 6. Alerts & Human-in-the-Loop Decision Support
- `GET /api/v1/alerts` - Active alerts filtered by severity and status (`page`, `page_size`)
- `PATCH /api/v1/alerts/<id>/status` - Acknowledge, triage, action, or resolve alert *(Requires auth: `ADMIN`, `HEALTH_OFFICER`)*
- `GET /api/v1/recommendations` - AI redistribution recommendations (`page`, `page_size`)
- `POST /api/v1/recommendations/generate` - Trigger redistribution optimizer grid scan *(Requires auth)*
- `POST /api/v1/recommendations/<id>/approve` - Human officer approval executing inventory dispatch *(Requires auth: `ADMIN`, `HEALTH_OFFICER`)*
- `POST /api/v1/recommendations/<id>/reject` - Officer rejection with clinical justification *(Requires auth: `ADMIN`, `HEALTH_OFFICER`)*

#### 7. Emergency Simulation & Federated Learning
- `POST /api/v1/simulation/run` - Multi-stressor emergency what-if simulation *(Requires auth)*
- `GET /api/v1/federated/overview` - International BRICS coordinator status, participating country nodes
- `POST /api/v1/federated/run-round` - Trigger federated learning training & secure aggregation cycle *(Requires auth: `ADMIN`, `ML_ENGINEER`)*

#### 8. Offline Sync & Cryptographic Audit Chain
- `POST /api/v1/sync/batch` - Idempotent sync of queued offline facility transactions *(Requires auth)*
- `GET /api/v1/audit/logs` - Paginated tamper-evident system activity and decision logs (`limit`, `page`, `page_size`)
- `GET /api/v1/audit/verify` - Verify cryptographic SHA-256 hash chaining integrity from genesis block
