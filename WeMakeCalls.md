# WeMakeCalls

> **Font:** BD Supper — used across all UI components, headings, labels, and text  
> **Colour Palette:** Lime `#BFFF00` and Black `#0A0A0A`

---

## Overview

**WeMakeCalls** is a full-stack MLOps application that simulates a call center environment, collects real-time call data, and uses machine learning to forecast future call volumes. The system is composed of four coordinated services — a call simulator, a Java backend for ML orchestration, a Python ML service, and a unified Angular frontend — all running as Docker containers.

---

## What the Application Does

- Simulates real call center interactions via a phone-style UI (call, hang up, rate agent)
- Tracks call duration, hangup reasons, and agent ratings in real time
- Aggregates call data hourly and feeds it into an ML forecasting pipeline
- Predicts how many calls will arrive in the next hour so managers can schedule agents
- Displays live predictions vs actual call counts on an interactive dashboard

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         WeMakeCalls                                  │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │               Angular + PrimeNG Frontend                    │   │
│   │   /dashboard (ML charts)   /call-simulator   /agents        │   │
│   └────────────┬───────────────────────────┬────────────────────┘   │
│                │                           │                         │
│                ▼                           ▼                         │
│   ┌────────────────────┐     ┌─────────────────────────────────┐    │
│   │  Java / Spring Boot│     │   C# / ASP.NET Core             │    │
│   │  ML Backend        │     │   Call Service                  │    │
│   │  - Predictions API │     │   - Agent availability          │    │
│   │  - ML scheduling   │     │   - Call session management     │    │
│   │  - PostgreSQL reads│     │   - Hangup reasons & ratings    │    │
│   └────────┬───────────┘     │   - SignalR (real-time timer)   │    │
│            │                 └──────────────┬──────────────────┘    │
│            │                                │                        │
│            ▼                                ▼                        │
│   ┌─────────────────┐          ┌────────────────────────────┐       │
│   │   PostgreSQL    │          │         MongoDB             │       │
│   │  - call_logs    │◄─ sync ──│  - live call sessions      │       │
│   │  - agents       │  (nightly│  - hangup reasons          │       │
│   │  - shifts       │   job)   │  - agent ratings           │       │
│   │  - predictions  │          │  - simulator events        │       │
│   └────────┬────────┘          └────────────────────────────┘       │
│            │                                                         │
│            ▼                                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              Python ML Service (Kedro + FastAPI)            │   │
│   │   Feature Engineering → Training → Inference → Predictions  │   │
│   └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
WeMakeCalls/
├── ml-service/                  ← Python / Kedro / FastAPI
│   ├── conf/
│   │   └── base/
│   │       ├── catalog.yml      # Dataset definitions
│   │       └── parameters.yml  # Model config, lag params, inference settings
│   ├── data/
│   │   ├── 01_raw/              # Raw call logs (CSV or Parquet)
│   │   ├── 03_primary/          # Inference batches
│   │   ├── 06_models/           # Saved trained models
│   │   └── 07_model_output/     # Predictions output
│   ├── src/
│   │   └── wemakecalls/
│   │       └── pipelines/
│   │           ├── nodes.py         # All ML functions
│   │           ├── feature_eng.py   # Feature engineering pipeline
│   │           ├── training.py      # Training pipeline
│   │           └── inference.py     # Inference pipeline
│   └── entrypoints/
│       ├── training.py          # Runs training pipeline
│       ├── inference.py         # Runs rolling inference
│       └── api.py               # FastAPI server
│
├── java-backend/                ← Spring Boot
│   └── src/main/java/
│       ├── controllers/         # REST endpoints
│       ├── services/            # Business logic
│       ├── repositories/        # JPA repositories
│       ├── models/              # JPA entities
│       └── scheduler/           # Hourly inference trigger
│
├── call-service/                ← C# / ASP.NET Core
│   └── src/
│       ├── Controllers/         # Call, Agent, Feedback endpoints
│       ├── Hubs/                # SignalR hub (real-time timer)
│       ├── Services/            # Call session logic
│       └── Models/              # MongoDB document models
│
├── frontend/                    ← Angular + PrimeNG
│   └── src/app/
│       ├── dashboard/           # ML predictions charts
│       ├── call-simulator/      # Phone UI (call, hang up, rate)
│       ├── agents/              # Agent management view
│       └── shared/              # Shared components, services
│
└── docker-compose.yml           ← Orchestrates all services
```

---

## Full Tech Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| **Angular** | 17+ | SPA framework, routing, component architecture |
| **PrimeNG** | 17+ | UI component library (buttons, tables, charts, dialogs, rating) |
| **PrimeFlex** | 3+ | CSS utility classes for layout |
| **Plotly.js** | latest | Interactive prediction charts |
| **@microsoft/signalr** | 7+ | Real-time call timer from C# SignalR hub |
| **RxJS** | 7+ | Reactive streams, WebSocket handling |
| **TypeScript** | 5+ | Typed JavaScript |
| **Font: BD Supper** | — | Primary font across all UI |
| **Colours** | — | Lime `#BFFF00` · Black `#0A0A0A` |

**Key PrimeNG Components Used**

| Component | Used For |
|---|---|
| `p-button` | Call and Hang Up buttons |
| `p-dialog` | Hangup reason popup |
| `p-radioButton` | 5 hangup reason options |
| `p-rating` | Agent star rating (1–5) |
| `p-chart` | Predictions vs actual chart |
| `p-table` | Call history, agent list |
| `p-badge` / `p-chip` | Agent availability status |
| `p-toast` | Notifications |
| `p-progressBar` | Call duration indicator |

---

### Call Service (C#)

| Technology | Version | Purpose |
|---|---|---|
| **ASP.NET Core Web API** | .NET 8 | REST API for call simulation |
| **SignalR** | .NET 8 | Real-time call timer pushed to Angular |
| **MongoDB.Driver** | 2.x | MongoDB C# driver |
| **AutoMapper** | 12+ | DTO mapping |
| **FluentValidation** | 11+ | Request validation |
| **Serilog** | 3+ | Structured logging |
| **Docker** | — | Containerisation |

**C# API Endpoints**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/agents/available` | Returns agents currently on shift |
| `POST` | `/calls/start` | Assigns available agent, starts session |
| `POST` | `/calls/end/{callId}` | Records end time, calculates duration |
| `POST` | `/calls/feedback/{callId}` | Saves hangup reason + agent rating |
| `GET` | `/calls/history` | Returns recent call documents |

**MongoDB Collections**

```json
// calls collection
{
  "_id": "ObjectId",
  "agentId": "string",
  "agentName": "string",
  "callStarted": "ISODate",
  "callEnded": "ISODate",
  "durationSeconds": "number",
  "hangupReason": "string",
  "agentRating": "number (1-5)",
  "status": "string (active | completed)"
}
```

**Hangup Reasons (5 options)**
1. Issue Resolved
2. Wrong Department
3. Long Wait Time
4. Call Dropped
5. Other

---

### Java Backend (Spring Boot)

| Technology | Version | Purpose |
|---|---|---|
| **Spring Boot** | 3.x | Application framework |
| **Spring Web** | 3.x | REST API |
| **Spring Data JPA** | 3.x | PostgreSQL ORM |
| **Spring Scheduler** | 3.x | Triggers hourly inference via FastAPI |
| **Spring WebSocket** | 3.x | Pushes predictions to Angular |
| **Hibernate** | 6.x | JPA implementation |
| **Flyway** | 9+ | Database migrations |
| **Lombok** | 1.18+ | Boilerplate reduction |
| **MapStruct** | 1.5+ | DTO mapping |
| **OpenFeign** | 4+ | HTTP client to call Python FastAPI |
| **Docker** | — | Containerisation |

**Spring Boot API Endpoints**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/predictions/latest` | Latest ML prediction |
| `GET` | `/predictions/history` | Historical predictions |
| `GET` | `/calls/hourly` | Hourly aggregated call counts |
| `POST` | `/ml/trigger-inference` | Manually trigger inference |
| `GET` | `/metrics` | Latest model evaluation metrics |

**PostgreSQL Tables**

```sql
agents         (id, name, email, is_active)
shifts         (id, agent_id, shift_start, shift_end, date)
call_logs      (id, started_at, ended_at, duration_seconds,
                hangup_reason, agent_rating, agent_id, hour_bucket,
                source)           -- 'csv_import' | 'simulator'
predictions    (id, predicted_at, target_hour, predicted_calls,
                actual_calls, model_type, mae, rmse)
```

---

### ML Service (Python)

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.12 | Core language |
| **Kedro** | 1.1+ | ML pipeline orchestration |
| **FastAPI** | 0.110+ | Exposes model as REST API |
| **Uvicorn** | 0.29+ | ASGI server for FastAPI |
| **CatBoost** | 1.2+ | Default gradient boosting model |
| **XGBoost** | 2.0+ | Alternative gradient boosting model |
| **LightGBM** | 4.0+ | Alternative gradient boosting model |
| **scikit-learn** | 1.3+ | Random Forest, Linear Regression, metrics |
| **pandas** | 2.0+ | Data manipulation |
| **NumPy** | 1.24+ | Numerical operations |
| **PyArrow** | 14.0+ | Parquet file support |
| **SQLAlchemy** | 2.0+ | PostgreSQL connection from Python |
| **psycopg2** | 2.9+ | PostgreSQL driver |
| **joblib** | 1.3+ | Model serialisation (non-CatBoost) |
| **Streamlit** | 1.30+ | Internal ML monitoring dashboard |
| **Dash** | 4.1+ | Predicted vs actual call volume dashboard |
| **uv** | latest | Python package manager |
| **pytest** | 7+ | Testing |
| **Ruff** | 0.3+ | Linting |

**ML Pipelines**

| Pipeline | Steps |
|---|---|
| **CSV Ingestion** | Read CSV → validate columns → clean nulls → normalise → insert into PostgreSQL call_logs |
| **Feature Engineering** | Rename columns → create lag features (1h, 2h, 24h, 168h) → calendar features (hour, day of week, is_weekend, is_holiday) → rolling averages |
| **Training** | Create target (next hour call count) → train/test split 80/20 → train model → evaluate (MAE, RMSE, MAPE) → save model |
| **Inference** | Load model → load latest batch → predict → append to predictions table |

**Supported Models**

| Model | Library | Notes |
|---|---|---|
| CatBoost | `catboost` | Default |
| XGBoost | `xgboost` | Alternative |
| LightGBM | `lightgbm` | Alternative |
| Random Forest | `scikit-learn` | Alternative |
| Linear Regression | `scikit-learn` | Baseline |

**FastAPI Endpoint**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict` | Accepts feature batch, returns prediction |
| `GET` | `/health` | Health check |
| `GET` | `/model/info` | Current model type and metrics |

**Dash Dashboard (port 8050)**

| Feature | Description |
|---|---|
| Predicted vs Actual chart | Line chart comparing forecasted and actual call counts per hour |
| Lookback slider | Configurable window: 6h, 12h, 24h, 48h, 3d, 5d, 7d |
| Metric cards | Avg actual/hr, avg predicted/hr, total predictions |
| Auto-refresh | Updates every 60 seconds |

---

### Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| **Docker** | Containerise all services |
| **Docker Compose** | Orchestrate all containers locally |
| **PostgreSQL 16** | Primary relational database |
| **MongoDB 7** | Call simulator document store |
| **Redis** *(optional)* | Cache latest predictions for fast dashboard reads |
| **Nginx** *(optional)* | Reverse proxy for production |

**Docker Services**

```yaml
services:
  ml-service        # Python / Kedro / FastAPI  — port 8000
  ml-dashboard      # Dash (predicted vs actual)— port 8050
  java-backend      # Spring Boot               — port 8080
  call-service      # C# ASP.NET Core           — port 5000
  frontend          # Angular (served by Nginx) — port 4200
  postgres          # PostgreSQL 16             — port 5432
  mongodb           # MongoDB 7                 — port 27017
```

---

## Data Flow

### Historical Data (CSV Import)

```
CSV files (historical call logs)
        ↓
Python ingestion script (pandas reads CSV)
        ↓
Validate + clean + normalise columns
        ↓
Insert into PostgreSQL call_logs (source = 'csv_import')
        ↓
ML pipeline reads from PostgreSQL for training
```

### Live Simulator Data

```
1. User opens /call-simulator in Angular
2. Clicks [Call] → C# assigns available agent → MongoDB: call session created
3. SignalR pushes timer ticks to Angular every second
4. User clicks [Hang Up] → dialog appears
5. User selects hangup reason + rates agent → C# saves to MongoDB
6. Nightly sync job aggregates MongoDB call docs → inserts into PostgreSQL call_logs (source = 'simulator')
7. Spring Boot scheduler triggers Python FastAPI /predict every hour
8. Python Kedro inference pipeline runs → prediction saved to PostgreSQL
9. Angular /dashboard polls Spring Boot → renders live chart (predicted vs actual)
```

---

## Historical Data — CSV Format

CSV files are the source of historical call data used to train the ML model. They are loaded once via a Python ingestion script and stored in PostgreSQL.

**Expected CSV columns**

| Column | Type | Description |
|---|---|---|
| `call_id` | string | Unique call identifier |
| `datetime` | datetime | Call start timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `duration_seconds` | integer | Total call duration |
| `queue_name` | string | Department or queue (e.g. billing, support) |
| `agent_id` | string | Agent who handled the call |
| `wait_time_seconds` | integer | Time caller waited before agent answered |
| `abandoned` | boolean | Whether caller hung up before being answered |
| `hangup_reason` | string | Reason for ending the call (optional in historical data) |

**Example CSV row**

```csv
call_id,datetime,duration_seconds,queue_name,agent_id,wait_time_seconds,abandoned
C1001,2024-01-15 08:03:00,245,billing,A12,32,false
C1002,2024-01-15 08:07:00,180,support,A07,15,false
C1003,2024-01-15 08:11:00,0,billing,—,120,true
```

**CSV files location in project**

```
ml-service/
└── data/
    └── 01_raw/
        ├── call_history_2023.csv
        ├── call_history_2024.csv
        └── ...
```

**Ingestion command**

```bash
python entrypoints/ingest_csv.py --file data/01_raw/call_history_2024.csv
```

The ingestion script validates columns, handles missing values, and inserts rows into PostgreSQL `call_logs` with `source = 'csv_import'`. The ML training pipeline then reads from that table.

---

Raw call logs are aggregated by hour, then these features are created:

| Feature | Description |
|---|---|
| `calls_lag_1h` | Calls received 1 hour ago |
| `calls_lag_2h` | Calls received 2 hours ago |
| `calls_lag_24h` | Same hour yesterday |
| `calls_lag_168h` | Same hour last week |
| `hour_of_day` | 0–23 |
| `day_of_week` | 0 (Mon) – 6 (Sun) |
| `is_weekend` | Boolean |
| `is_holiday` | Boolean |
| `rolling_avg_7d` | Average calls at this hour over last 7 days |
| `avg_duration_lag_1h` | Average call duration 1 hour ago |
| `abandonment_rate_lag_1h` | Abandonment rate 1 hour ago |

---

## UI Pages (Angular)

| Route | Description |
|---|---|
| `/dashboard` | Live predictions chart, model metrics, call volume history |
| `/call-simulator` | Phone UI — call button, hang up, timer, hangup reason dialog, agent rating |
| `/agents` | Agent list, availability status, shift schedule |
| `/history` | Call history table with filters |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/your-org/WeMakeCalls.git
cd WeMakeCalls

# Start all services
docker compose up

# Services available at:
# Angular Dashboard     → http://localhost:4200
# Spring Boot API       → http://localhost:8080
# C# Call Service       → http://localhost:5000
# Python ML API         → http://localhost:8000
# ML API Docs (Swagger) → http://localhost:8000/docs
# ML Dashboard (Dash)   → http://localhost:8050
# pgAdmin               → http://localhost:5050
```

---

## Configuration

| File | Controls |
|---|---|
| `ml-service/conf/base/parameters.yml` | Model type, lag params, inference interval |
| `java-backend/src/main/resources/application.yml` | DB connections, scheduler interval |
| `call-service/appsettings.json` | MongoDB connection, SignalR config |
| `frontend/src/environments/environment.ts` | API base URLs |
| `docker-compose.yml` | All service ports and volumes |

---

## Evaluation Metrics

| Metric | Description |
|---|---|
| **MAE** | Mean Absolute Error — average prediction error in number of calls |
| **RMSE** | Root Mean Squared Error — penalises large errors more |
| **MAPE** | Mean Absolute Percentage Error — error as a percentage |

---

*WeMakeCalls — BD Supper font · Lime `#BFFF00` · Black `#0A0A0A`*
