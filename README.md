# WeMakeCalls

WeMakeCalls is a Docker-first call center simulation platform with a Spring Boot call service, a Python ML service, a live Dash forecast dashboard, and an Angular frontend.

## Start With Docker

Prerequisites:

- Docker Desktop or Docker Engine with Docker Compose
- Git

Run the full stack from the repository root:

```bash
git clone https://github.com/your-org/WeMakeCalls.git
cd WeMakeCalls
docker compose up --build -d
```

Seed the agents collection after the containers are up:

PowerShell:

```powershell
Get-Content .\seed-agents.js | docker exec -i database_mongodb mongosh call-service
```

bash or zsh:

```bash
cat ./seed-agents.js | docker exec -i database_mongodb mongosh call-service
```

Confirm container status:

```bash
docker compose ps
```

This startup path uses Docker only. You do not need local Java, Node.js, Python, MongoDB, or PostgreSQL installed to run the application.

## Service URLs

Open these once `docker compose ps` shows the services are running:

| Service | URL |
|---|---|
| Angular frontend | http://localhost:4200 |
| Call service API | http://localhost:5000 |
| ML API | http://localhost:8000 |
| ML API docs | http://localhost:8000/docs |
| ML dashboard | http://localhost:8050 |
| Mongo Express | http://localhost:8081 |
| pgAdmin | http://localhost:5050 |

Notes:

- On first startup, the ML dashboard can take up to a minute to finish booting.
- PostgreSQL is exposed on host port `5433`.
- MongoDB is exposed on host port `27017`.

## What Starts

`docker compose up --build -d` starts these services:

| Service | Port | Purpose |
|---|---|---|
| `frontend-app` | 4200 | Angular UI for the simulator and dashboard views |
| `call-service` | 5000 | Spring Boot API for calls, agents, and WebSocket updates |
| `ml-service` | 8000 | FastAPI ML API |
| `ml-dashboard` | 8050 | Dash app for live forecast vs actuals |
| `mongodb` | 27017 | Operational call data |
| `postgresql` | 5433 | Analytics and prediction storage |
| `mongo-express` | 8081 | MongoDB admin UI |
| `pgadmin` | 5050 | PostgreSQL admin UI |

## First Check

1. Open the Angular frontend at `http://localhost:4200`.
2. Go to the call simulator and start a call.
3. Confirm agents were seeded and a call can be assigned.
4. Open the ML dashboard at `http://localhost:8050` and verify the live chart loads.

## Stop The Stack

```bash
docker compose down
```

To remove containers and volumes for a full reset:

```bash
docker compose down -v
```

## Tech Stack

- Frontend: Angular 21, PrimeNG
- Call service: Java 17, Spring Boot 4, MongoDB, PostgreSQL
- ML service: Python 3.12, FastAPI, Kedro, CatBoost
- Dashboard: Dash, Plotly
- Infrastructure: Docker, Docker Compose
