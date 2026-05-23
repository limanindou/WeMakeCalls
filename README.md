<<<<<<< HEAD
# WeMakeCalls — AI-Powered Call Center Platform

A production-grade call center simulation platform with real-time ML forecasting.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Frontend   │────▶│ Call Service  │────▶│   MongoDB   │
│  (Angular)  │     │ (Spring Boot)│     │  (calls DB) │
│  :4200      │     │    :5000     │     │   :27017    │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │  PostgreSQL  │◀────│  ML Service  │
                    │  (analytics) │     │  (FastAPI)   │
                    │    :5432     │     │    :8000     │
                    └──────────────┘     └──────┬───────┘
                                                │
                                         ┌──────▼───────┐
                                         │ ML Dashboard │
                                         │   (Dash)     │
                                         │    :8050     │
                                         └──────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 4200 | Angular app — call simulator + dashboard |
| Call Service | 5000 | REST API + WebSocket for call management |
| ML Service | 8000 | FastAPI — call volume prediction API |
| ML Dashboard | 8050 | Real-time forecasting chart (updates every 1s) |
| MongoDB | 27017 | Live call data storage |
| PostgreSQL | 5432 | Analytics + synced call history |
| Mongo Express | 8081 | MongoDB admin UI |
| pgAdmin | 5050 | PostgreSQL admin UI |

## Quick Start

```bash
docker-compose up --build
```

Then seed agents:
```bash
mongosh mongodb://localhost:27017/call-service seed-agents.js
```

## ML Model

**Problem**: Predict call volume for the next hour to optimize agent staffing.

**Features**:
- `calls_lag_1h`, `calls_lag_2h`, `calls_lag_24h`, `calls_lag_168h` — historical call counts
- `hour_of_day`, `day_of_week`, `is_weekend`, `is_holiday` — temporal features
- `rolling_avg_7d` — 7-day rolling average
- `avg_duration_lag_1h`, `abandonment_rate_lag_1h` — quality metrics

**Model**: CatBoost (gradient boosting)

**Inference**: Runs every 1 second (simulating 1 hour per second) with results displayed on the real-time dashboard at http://localhost:8050

## Monitoring

- `/health` — service health check
- `/metrics` — prediction count, model status, uptime
- `/model/info` — model metadata (type, trained_at, MAE, RMSE, MAPE)

## Tech Stack

- **Backend**: Java 17, Spring Boot 4.0.6, MongoDB, PostgreSQL
- **ML**: Python 3.12, CatBoost, FastAPI, Dash/Plotly
- **Frontend**: Angular 21, PrimeNG, STOMP WebSocket
- **Infrastructure**: Docker, Docker Compose
"# WeMakeCalls" 
=======
# WeMakeCalls
>>>>>>> 53cb9d1461e729bb5b5aadc53cdcc10bb0194453
